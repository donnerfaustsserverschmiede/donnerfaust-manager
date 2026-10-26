from pathlib import Path
import json
"""Wirtschaft & Handel: Lager, Preise, Handel und Kassenbuch."""
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import discord
from discord import app_commands
from discord.ext import commands
from app.core.database import DB_PATH
from app.modules.trade.overview import refresh as refresh_inventory_overview

log = logging.getLogger(__name__)

# OPSUCHT-Wirtschaft: Rollen für Mitarbeiter- und Verwaltungszugriff.
LEITUNG_ROLE_ID = 1564044141002752072
MITARBEITER_ROLE_ID = 1564043999877144616


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS trade_items (
            guild_id INTEGER NOT NULL, item_id INTEGER NOT NULL, name TEXT NOT NULL COLLATE NOCASE,
            category TEXT NOT NULL DEFAULT 'Sonstiges', stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),
            sell_price TEXT NOT NULL DEFAULT '0.00', buy_price TEXT NOT NULL DEFAULT '0.00',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(guild_id,item_id), UNIQUE(guild_id,name))""")
        db.execute("""CREATE TABLE IF NOT EXISTS trade_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, item_name TEXT NOT NULL,
            kind TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price TEXT NOT NULL, total TEXT NOT NULL,
            partner TEXT NOT NULL DEFAULT '', actor_id INTEGER NOT NULL, actor_name TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("""CREATE TABLE IF NOT EXISTS trade_cashbook (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, kind TEXT NOT NULL,
            amount TEXT NOT NULL, description TEXT NOT NULL, actor_id INTEGER NOT NULL,
            actor_name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def cash(value):
    try:
        value = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("Ungültiger Geldbetrag.")
    if not value.is_finite() or value < 0:
        raise ValueError("Beträge müssen gültig und nicht negativ sein.")
    return value


def fmt(value):
    return f"{Decimal(str(value)):,.2f} Coins".replace(",", "X").replace(".", ",").replace("X", ".")


def item_for(db, guild_id, name):
    return db.execute("SELECT * FROM trade_items WHERE guild_id=? AND name=? COLLATE NOCASE",
                      (guild_id, name.strip())).fetchone()


def book(db, guild_id, kind, amount, description, user):
    db.execute("INSERT INTO trade_cashbook(guild_id,kind,amount,description,actor_id,actor_name) VALUES(?,?,?,?,?,?)",
               (guild_id, kind, str(amount), description[:500], user.id, str(user)[:100]))


async def item_autocomplete(interaction: discord.Interaction, current: str):
    """Filter inventory choices by the beginning of the entered article name."""
    if not interaction.guild:
        return []

    search = current.strip()
    try:
        init_db()
        with connect() as db:
            rows = db.execute(
                """SELECT name, stock FROM trade_items
                   WHERE guild_id = ? AND name LIKE ? COLLATE NOCASE
                   ORDER BY name COLLATE NOCASE LIMIT 25""",
                (interaction.guild.id, f"{search}%"),
            ).fetchall()
        return [
            app_commands.Choice(
                name=f"{row['name']} · Bestand {row['stock']}"[:100],
                value=row["name"][:100],
            )
            for row in rows
        ]
    except (sqlite3.Error, TypeError, ValueError):
        log.exception("Item autocomplete failed for guild %s", interaction.guild.id)
        return []


class TradeModule(commands.Cog):
    @app_commands.command(name="minecraft_items_importieren", description="Importiert alle Standard-Items aus Minecraft Java 1.21.4 mit Bestand 0.")
    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID)
    async def minecraft_items_importieren(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        source = Path(__file__).resolve().parents[3] / "data" / "minecraft_items_1_21_4.json"
        try:
            items = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.exception("Minecraft item list could not be loaded")
            return await interaction.response.send_message("Die Minecraft-Itemliste konnte nicht geladen werden.", ephemeral=True)
        added = 0
        skipped = 0
        with connect() as db:
            next_id = db.execute("SELECT COALESCE(MAX(item_id),0)+1 FROM trade_items WHERE guild_id=?", (interaction.guild.id,)).fetchone()[0]
            for item in items:
                if item_for(db, interaction.guild.id, item["name"]):
                    skipped += 1
                    continue
                db.execute(
                    "INSERT INTO trade_items(guild_id,item_id,name,category,stock,sell_price,buy_price) VALUES(?,?,?,?,0,?,?)",
                    (interaction.guild.id, next_id, item["name"], item.get("category", "Sonstiges"), "0.00", "0.00"),
                )
                next_id += 1
                added += 1
            book(db, interaction.guild.id, "INFO", 0, f"Minecraft-Standarditems importiert: {added} neu, {skipped} bereits vorhanden", interaction.user)
        await interaction.response.send_message(
            f"Minecraft Java 1.21.4: **{added}** Artikel neu angelegt, **{skipped}** bereits vorhanden übersprungen. Alle neuen Bestände sind **0**; Preise stehen zunächst auf 0,00.",
            ephemeral=True,
        )
        await self.send_log(interaction, "Minecraft-Items importiert", f"Neu: {added}\\nÜbersprungen: {skipped}\\nVersion: Java 1.21.4")


    def __init__(self, bot):
        self.bot = bot
        init_db()

    @app_commands.command(name="lageruebersicht_aktualisieren", description="Erstellt oder aktualisiert die dauerhafte Lagerliste.")
    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID)
    async def lageruebersicht_aktualisieren(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await refresh_inventory_overview(self.bot, interaction.guild.id)
        await interaction.followup.send("Lagerübersicht wurde aktualisiert.", ephemeral=True)

    async def send_log(self, interaction, title, description):
        try:
            from app.core.database import get_guild_setting
            guild = interaction.guild
            channel_id = get_guild_setting(guild.id, "log_channel_id") if guild else None
            channel = guild.get_channel(int(channel_id)) if channel_id and guild else None
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=discord.Embed(title=title, description=description[:3900],
                    color=discord.Color.gold(), timestamp=datetime.now(timezone.utc)))
        except Exception:
            log.exception("Trade log delivery failed")

    @app_commands.command(name="artikel_anlegen", description="Legt einen Artikel im zentralen Lager an.")
    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID)
    async def artikel_anlegen(self, interaction: discord.Interaction, name: str, kategorie: str = "Sonstiges",
                              verkaufspreis: app_commands.Range[float, 0.0, 100000000.0] = 0,
                              einkaufspreis: app_commands.Range[float, 0.0, 100000000.0] = 0):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        name = name.strip()
        if not name or len(name) > 80:
            return await interaction.response.send_message("Der Artikelname muss 1–80 Zeichen lang sein.", ephemeral=True)
        try:
            sell, buy = cash(verkaufspreis), cash(einkaufspreis)
            with connect() as db:
                if item_for(db, interaction.guild.id, name):
                    return await interaction.response.send_message("Dieser Artikel existiert bereits.", ephemeral=True)
                next_id = db.execute("SELECT COALESCE(MAX(item_id),0)+1 FROM trade_items WHERE guild_id=?",
                                     (interaction.guild.id,)).fetchone()[0]
                db.execute("INSERT INTO trade_items(guild_id,item_id,name,category,sell_price,buy_price) VALUES(?,?,?,?,?,?)",
                           (interaction.guild.id, next_id, name, kategorie.strip()[:60] or "Sonstiges", str(sell), str(buy)))
                book(db, interaction.guild.id, "INFO", 0, f"Artikel angelegt: {name}", interaction.user)
            await interaction.response.send_message(f"Artikel **{discord.utils.escape_markdown(name)}** angelegt. Bestand: 0 · Verkauf: {fmt(sell)} · Einkauf: {fmt(buy)}")
            await self.send_log(interaction, "Artikel angelegt", f"{name}\nKategorie: {kategorie}\nVon: {interaction.user.mention}")
        except (ValueError, sqlite3.Error):
            log.exception("Create item failed")
            await interaction.response.send_message("Artikel konnte nicht angelegt werden. Prüfe Name und Preise.", ephemeral=True)

    @app_commands.command(name="lagerbestand", description="Öffnet das interaktive Lager.")
    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    async def lagerbestand(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        view = InventoryView(self, interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="artikel_loeschen", description="Löscht einen Lagerartikel mit Bestand 0.")
    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID)
    async def artikel_loeschen(self, interaction: discord.Interaction, artikel: str):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            item = item_for(db, interaction.guild.id, artikel)
            if not item:
                return await interaction.response.send_message("Artikel nicht gefunden.", ephemeral=True)
            if item["stock"] != 0:
                return await interaction.response.send_message("Löschen ist nur bei Bestand 0 möglich. Buche den Bestand zuerst aus.", ephemeral=True)
            db.execute("DELETE FROM trade_items WHERE guild_id=? AND item_id=?", (interaction.guild.id, item["item_id"]))
            book(db, interaction.guild.id, "INFO", 0, f"Artikel gelöscht: {item['name']}", interaction.user)
        await interaction.response.send_message(f"Artikel **{discord.utils.escape_markdown(item['name'])}** gelöscht.", ephemeral=True)
        await self.send_log(interaction, "Lagerartikel gelöscht", f"{item['name']} · von {interaction.user.mention}")

    async def change_stock(self, interaction, artikel, menge, delta, notiz=""):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            item = item_for(db, interaction.guild.id, artikel)
            if not item:
                return await interaction.response.send_message("Artikel nicht gefunden. Prüfe /lagerbestand.", ephemeral=True)
            after = item["stock"] + delta * menge
            if after < 0:
                return await interaction.response.send_message(f"Nicht genug Bestand. Vorhanden: {item['stock']}.", ephemeral=True)
            db.execute("UPDATE trade_items SET stock=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND item_id=?",
                       (after, interaction.guild.id, item["item_id"]))
            db.execute("INSERT INTO trade_transactions(guild_id,item_name,kind,quantity,unit_price,total,actor_id,actor_name,note) VALUES(?,?,?,?,?,?,?,?,?)",
                       (interaction.guild.id, item["name"], "EINLAGERUNG" if delta > 0 else "AUSLAGERUNG", menge, "0", "0", interaction.user.id, str(interaction.user), notiz))
            book(db, interaction.guild.id, "INFO", 0, f"Lager {item['name']}: {item['stock']} -> {after}; {notiz}", interaction.user)
        await interaction.response.send_message(f"**{item['name']}**: {item['stock']} → **{after}** Stück.")
        await refresh_inventory_overview(self.bot, interaction.guild.id)
        await self.send_log(interaction, "Lagerbewegung", f"Artikel: {item['name']}\nÄnderung: {delta*menge:+}\nBestand: {item['stock']} → {after}\nVon: {interaction.user.mention}\nNotiz: {notiz or '–'}")

    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="einlagern", description="Bucht Ressourcen ins Lager.")
    async def einlagern(self, interaction: discord.Interaction, artikel: str,
                        menge: app_commands.Range[int, 1, 100000000], notiz: str = ""):
        await self.change_stock(interaction, artikel, menge, 1, notiz)

    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="auslagern", description="Bucht Ressourcen aus dem Lager aus.")
    async def auslagern(self, interaction: discord.Interaction, artikel: str,
                        menge: app_commands.Range[int, 1, 100000000], notiz: str = ""):
        await self.change_stock(interaction, artikel, menge, -1, notiz)

    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="preis_setzen", description="Setzt Verkaufspreis und optional Einkaufspreis.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def preis_setzen(self, interaction: discord.Interaction, artikel: str,
                           verkaufspreis: app_commands.Range[float, 0.0, 100000000.0],
                           einkaufspreis: app_commands.Range[float, 0.0, 100000000.0] | None = None):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        try:
            sell = cash(verkaufspreis)
            with connect() as db:
                item = item_for(db, interaction.guild.id, artikel)
                if not item:
                    return await interaction.response.send_message("Artikel nicht gefunden.", ephemeral=True)
                buy = cash(einkaufspreis) if einkaufspreis is not None else cash(item["buy_price"])
                db.execute("UPDATE trade_items SET sell_price=?,buy_price=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND item_id=?",
                           (str(sell), str(buy), interaction.guild.id, item["item_id"]))
                book(db, interaction.guild.id, "INFO", 0, f"Preise {item['name']}: Verkauf {sell}; Einkauf {buy}", interaction.user)
            await interaction.response.send_message(f"Preise für **{item['name']}**: Verkauf {fmt(sell)} · Einkauf {fmt(buy)}")
            await self.send_log(interaction, "Preis geändert", f"{item['name']}\nVerkauf: {fmt(sell)} · Einkauf: {fmt(buy)}\nVon: {interaction.user.mention}")
        except (ValueError, sqlite3.Error):
            log.exception("Price update failed")
            await interaction.response.send_message("Preis konnte nicht gespeichert werden.", ephemeral=True)

    async def trade(self, interaction, artikel, menge, partner, einzelpreis, kind):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        try:
            with connect() as db:
                item = item_for(db, interaction.guild.id, artikel)
                if not item:
                    return await interaction.response.send_message("Artikel nicht gefunden.", ephemeral=True)
                unit = cash(einzelpreis)
                if unit <= 0:
                    return await interaction.response.send_message("Der vereinbarte Stückpreis muss größer als 0 sein.", ephemeral=True)
                total = (unit * menge).quantize(Decimal("0.01"))
                after = item["stock"] + (menge if kind == "EINKAUF" else -menge)
                if after < 0:
                    return await interaction.response.send_message(f"Verkauf abgebrochen: nur {item['stock']} Stück auf Lager.", ephemeral=True)
                db.execute("UPDATE trade_items SET stock=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND item_id=?",
                           (after, interaction.guild.id, item["item_id"]))
                db.execute("INSERT INTO trade_transactions(guild_id,item_name,kind,quantity,unit_price,total,partner,actor_id,actor_name) VALUES(?,?,?,?,?,?,?,?,?)",
                           (interaction.guild.id, item["name"], kind, menge, str(unit), str(total), partner[:150], interaction.user.id, str(interaction.user)))
                book(db, interaction.guild.id, "EINNAHME" if kind == "VERKAUF" else "AUSGABE", total,
                     f"{kind}: {menge} x {item['name']} @ {fmt(unit)} · Partner: {partner}", interaction.user)
            await interaction.response.send_message(f"**{kind.title()} gebucht**\nArtikel: {item['name']} × {menge}\nPartner: {discord.utils.escape_markdown(partner)}\nEinzelpreis: {fmt(unit)}\nGesamt: **{fmt(total)}**\nBestand: {item['stock']} → **{after}**")
            await self.send_log(interaction, f"{kind.title()} gebucht", f"{item['name']} × {menge}\nPartner: {partner}\nGesamt: {fmt(total)}\nBestand: {item['stock']} → {after}\nVon: {interaction.user.mention}")
        except (ValueError, sqlite3.Error):
            log.exception("Trade failed")
            await interaction.response.send_message("Buchung fehlgeschlagen. Prüfe Eingaben und Datenbank.", ephemeral=True)

    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="verkauf", description="Verkauf mit dem manuell vereinbarten Stückpreis buchen.")
    async def verkauf(self, interaction: discord.Interaction, artikel: str,
                      menge: app_commands.Range[int, 1, 100000000], kunde: str,
                      einzelpreis: app_commands.Range[float, 0.01, 100000000.0]):
        await self.trade(interaction, artikel, menge, kunde, einzelpreis, "VERKAUF")

    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    @app_commands.autocomplete(artikel=item_autocomplete)
    @app_commands.command(name="einkauf", description="Einkauf mit dem manuell vereinbarten Stückpreis buchen.")
    async def einkauf(self, interaction: discord.Interaction, artikel: str,
                      menge: app_commands.Range[int, 1, 100000000], lieferant: str,
                      einzelpreis: app_commands.Range[float, 0.01, 100000000.0]):
        await self.trade(interaction, artikel, menge, lieferant, einzelpreis, "EINKAUF")

    @app_commands.command(name="startkapital", description="Erfasst das vorhandene Startkapital einmalig im Kassenbuch.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def startkapital(self, interaction: discord.Interaction, betrag: app_commands.Range[float, 0.01, 100000000.0], notiz: str = "Anfangsbestand"):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        try:
            amount = cash(betrag)
            with connect() as db:
                exists = db.execute("SELECT 1 FROM trade_cashbook WHERE guild_id=? AND kind='KAPITAL' LIMIT 1", (interaction.guild.id,)).fetchone()
                if exists:
                    return await interaction.response.send_message("Startkapital wurde bereits erfasst. Weitere Korrekturen bitte über /kassenbuch_buchen buchen.", ephemeral=True)
                book(db, interaction.guild.id, "KAPITAL", amount, f"Startkapital: {notiz}", interaction.user)
            await interaction.response.send_message(f"Startkapital von **{fmt(amount)}** wurde erfasst. Es wird separat vom operativen Umsatz ausgewiesen.", ephemeral=True)
            await self.send_log(interaction, "Startkapital erfasst", f"Betrag: {fmt(amount)}\nNotiz: {notiz}\nVon: {interaction.user.mention}")
        except (ValueError, sqlite3.Error):
            log.exception("Starting capital entry failed")
            await interaction.response.send_message("Startkapital konnte nicht erfasst werden.", ephemeral=True)

    @app_commands.command(name="kassenbuch_buchen", description="Erfasst eine sonstige Einnahme oder Ausgabe.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(art=[
        app_commands.Choice(name="Einnahme", value="EINNAHME"),
        app_commands.Choice(name="Ausgabe", value="AUSGABE"),
    ])
    async def kassenbuch_buchen(self, interaction: discord.Interaction,
                                art: app_commands.Choice[str],
                                betrag: app_commands.Range[float, 0.01, 100000000.0],
                                beschreibung: str):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        try:
            amount = cash(betrag)
            description = beschreibung.strip()
            if not description:
                return await interaction.response.send_message("Bitte eine Beschreibung angeben.", ephemeral=True)
            with connect() as db:
                book(db, interaction.guild.id, art.value, amount, description, interaction.user)
            await interaction.response.send_message(f"{art.name} von **{fmt(amount)}** wurde im Kassenbuch erfasst.", ephemeral=True)
            await self.send_log(interaction, f"Kassenbuch: {art.name}", f"Betrag: {fmt(amount)}\nBeschreibung: {description}\nVon: {interaction.user.mention}")
        except (ValueError, sqlite3.Error):
            log.exception("Manual cashbook entry failed")
            await interaction.response.send_message("Kassenbuchung fehlgeschlagen.", ephemeral=True)

    @app_commands.command(name="bilanz", description="Zeigt Einnahmen, Ausgaben, Netto-Cashflow und Lagerwert.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bilanz(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            sums = db.execute("""SELECT
                COALESCE(SUM(CASE WHEN kind='EINNAHME' THEN CAST(amount AS REAL) ELSE 0 END),0) income,
                COALESCE(SUM(CASE WHEN kind='AUSGABE' THEN CAST(amount AS REAL) ELSE 0 END),0) expense,
                COALESCE(SUM(CASE WHEN kind='KAPITAL' THEN CAST(amount AS REAL) ELSE 0 END),0) capital
                FROM trade_cashbook WHERE guild_id=?""", (interaction.guild.id,)).fetchone()
            stock = db.execute("SELECT COUNT(*) n,COALESCE(SUM(stock),0) units,COALESCE(SUM(stock*CAST(buy_price AS REAL)),0) value FROM trade_items WHERE guild_id=?",
                               (interaction.guild.id,)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM trade_transactions WHERE guild_id=? AND kind IN ('VERKAUF','EINKAUF')",
                               (interaction.guild.id,)).fetchone()[0]
        income, expense = Decimal(str(sums["income"])), Decimal(str(sums["expense"]))
        embed = discord.Embed(title="📊 Handelsbilanz", color=discord.Color.gold())
        embed.add_field(name="Startkapital", value=fmt(sums["capital"]))
        embed.add_field(name="Operative Einnahmen", value=fmt(income))
        embed.add_field(name="Ausgaben", value=fmt(expense))
        embed.add_field(name="Netto-Cashflow", value=fmt(income-expense))
        embed.add_field(name="Kassenstand inkl. Startkapital", value=fmt(Decimal(str(sums["capital"])) + income - expense), inline=False)
        embed.add_field(name="Lagerwert (Einkaufspreise)", value=fmt(stock["value"]))
        embed.add_field(name="Artikel / Menge", value=f"{stock['n']} Artikel · {stock['units']} Stück")
        embed.add_field(name="Handelsvorgänge", value=str(count))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="kassenbuch", description="Zeigt die letzten Kassenbewegungen.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kassenbuch(self, interaction: discord.Interaction, seite: app_commands.Range[int, 1, 1000] = 1):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            rows = db.execute("SELECT * FROM trade_cashbook WHERE guild_id=? ORDER BY id DESC LIMIT 15 OFFSET ?",
                              (interaction.guild.id, (seite-1)*15)).fetchall()
            count = db.execute("SELECT COUNT(*) FROM trade_cashbook WHERE guild_id=?", (interaction.guild.id,)).fetchone()[0]
        if not rows:
            return await interaction.response.send_message("Noch keine Kassenbuchungen.", ephemeral=True)
        lines = [f"**#{r['id']} · {r['kind']} · {fmt(r['amount'])}**\n{r['description']}\n{r['created_at']} · {r['actor_name']}" for r in rows]
        embed = discord.Embed(title=f"📒 Kassenbuch · {count} Buchungen", description="\n\n".join(lines)[:4000], color=discord.Color.gold())
        embed.set_footer(text=f"Seite {seite}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="buchungen", description="Zeigt die letzten Lager-, Einkaufs- und Verkaufsvorgänge.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def buchungen(self, interaction: discord.Interaction, seite: app_commands.Range[int, 1, 1000] = 1):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            rows = db.execute("SELECT * FROM trade_transactions WHERE guild_id=? ORDER BY id DESC LIMIT 15 OFFSET ?",
                              (interaction.guild.id, (seite-1)*15)).fetchall()
        if not rows:
            return await interaction.response.send_message("Noch keine Vorgänge vorhanden.", ephemeral=True)
        lines = [f"**#{r['id']} · {r['kind']} · {r['item_name']} × {r['quantity']}** · {fmt(r['total'])}\n{r['created_at']} · {r['actor_name']} · {r['partner'] or r['note'] or '–'}" for r in rows]
        embed = discord.Embed(title="🧾 Lager- und Handelsbuchungen", description="\n\n".join(lines)[:4000], color=discord.Color.blurple())
        embed.set_footer(text=f"Seite {seite} · 15 Einträge je Seite")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.checks.has_any_role(LEITUNG_ROLE_ID, MITARBEITER_ROLE_ID)
    @app_commands.command(name="preisliste", description="Zeigt die eigene Preisliste aller Artikel.")
    async def preisliste(self, interaction: discord.Interaction, seite: app_commands.Range[int, 1, 1000] = 1):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            rows = db.execute("SELECT name,category,stock,sell_price FROM trade_items WHERE guild_id=? ORDER BY category,name",
                              (interaction.guild.id,)).fetchall()
        if not rows:
            return await interaction.response.send_message("Die Preisliste ist leer. Lege zuerst Artikel an.", ephemeral=True)
        pages = max(1, (len(rows)+24)//25)
        if seite > pages:
            return await interaction.response.send_message(f"Es gibt {pages} Seite(n).", ephemeral=True)
        lines = [f"**{discord.utils.escape_markdown(r['name'])}** · {r['category']} · {fmt(r['sell_price'])} · Bestand: {r['stock']}" for r in rows[(seite-1)*25:seite*25]]
        embed = discord.Embed(title="🪙 Eigene Handelspreisliste", description="\n".join(lines)[:4000], color=discord.Color.gold())
        embed.set_footer(text=f"Seite {seite}/{pages} · Preis pro Stück")
        await interaction.response.send_message(embed=embed)



class AddInventoryItemModal(discord.ui.Modal, title="Artikel hinzufügen"):
    name = discord.ui.TextInput(label="Artikelname", placeholder="z. B. Cobblestone", max_length=80)
    category = discord.ui.TextInput(label="Kategorie", placeholder="Bergbau, Holz, Kampf, Nahrung, Sonstiges, Besonderes", max_length=30)

    def __init__(self, module, guild_id, user_id):
        super().__init__()
        self.module, self.guild_id, self.user_id = module, guild_id, user_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id or not interaction.guild or interaction.guild.id != self.guild_id:
            return await interaction.response.send_message("Dieses Fenster gehört zu einer anderen Person.", ephemeral=True)
        name = str(self.name.value).strip()
        raw_category = str(self.category.value).strip().casefold()
        categories = {"bergbau":"Bergbau", "holz":"Holz", "kampf":"Kampf", "nahrung":"Nahrung", "sonstiges":"Sonstiges", "besonderes":"Besonderes"}
        if not name:
            return await interaction.response.send_message("Bitte einen Artikelnamen angeben.", ephemeral=True)
        if raw_category not in categories:
            return await interaction.response.send_message("Kategorie ungültig. Erlaubt: Bergbau, Holz, Kampf, Nahrung, Sonstiges, Besonderes.", ephemeral=True)
        try:
            with connect() as db:
                if item_for(db, self.guild_id, name):
                    return await interaction.response.send_message("Dieser Artikel existiert bereits.", ephemeral=True)
                next_id = db.execute("SELECT COALESCE(MAX(item_id),0)+1 FROM trade_items WHERE guild_id=?", (self.guild_id,)).fetchone()[0]
                db.execute("INSERT INTO trade_items(guild_id,item_id,name,category,stock,sell_price,buy_price) VALUES(?,?,?,?,0,'0.00','0.00')", (self.guild_id, next_id, name, categories[raw_category]))
                book(db, self.guild_id, "INFO", 0, f"Artikel angelegt: {name} ({categories[raw_category]})", interaction.user)
            await interaction.response.send_message(f"Artikel **{discord.utils.escape_markdown(name)}** wurde angelegt. Kategorie: {categories[raw_category]} · Startbestand: 0.", ephemeral=True)
            await self.module.send_log(interaction, "Lagerartikel angelegt", f"{name}\nKategorie: {categories[raw_category]}\nVon: {interaction.user.mention}")
        except sqlite3.Error:
            log.exception("Inventory item creation failed")
            await interaction.response.send_message("Artikel konnte nicht gespeichert werden.", ephemeral=True)


class StockMovementModal(discord.ui.Modal, title="Lagerbestand anpassen"):
    quantity = discord.ui.TextInput(label="Menge", placeholder="z. B. 64", max_length=9)

    def __init__(self, view):
        super().__init__()
        self.inventory_view = view

    async def on_submit(self, interaction: discord.Interaction):
        view = self.inventory_view
        if interaction.user.id != view.user_id:
            return await interaction.response.send_message("Dieses Lagerfenster gehört zu einer anderen Person.", ephemeral=True)
        if not view.selected_item or not view.selected_action:
            return await interaction.response.send_message("Bitte zuerst Artikel und Eingabe/Ausgabe auswählen.", ephemeral=True)
        try:
            quantity = int(str(self.quantity.value).strip())
            if quantity < 1 or quantity > 100000000:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("Die Menge muss eine ganze Zahl größer als 0 sein.", ephemeral=True)
        with connect() as db:
            item = item_for(db, view.guild_id, view.selected_item)
            if not item:
                return await interaction.response.send_message("Artikel nicht gefunden. Öffne /lagerbestand erneut.", ephemeral=True)
            delta = quantity if view.selected_action == "EINGANG" else -quantity
            after = item["stock"] + delta
            if after < 0:
                return await interaction.response.send_message(f"Nicht genug Bestand. Vorhanden: {item['stock']}.", ephemeral=True)
            db.execute("UPDATE trade_items SET stock=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND item_id=?", (after, view.guild_id, item["item_id"]))
            db.execute("INSERT INTO trade_transactions(guild_id,item_name,kind,quantity,unit_price,total,actor_id,actor_name,note) VALUES(?,?,?,?,?,?,?,?,?)", (view.guild_id, item["name"], "EINLAGERUNG" if delta > 0 else "AUSLAGERUNG", quantity, "0", "0", interaction.user.id, str(interaction.user), "Interaktives Lagerfenster"))
            book(db, view.guild_id, "INFO", 0, f"Lager {item['name']}: {item['stock']} -> {after}", interaction.user)
        await interaction.response.send_message(f"**{item['name']}**: {item['stock']} → **{after}** Stück gespeichert.", ephemeral=True)
        await view.module.send_log(interaction, "Lagerbestand angepasst", f"Artikel: {item['name']}\nAktion: {'Eingabe' if delta > 0 else 'Ausgabe'} {quantity}\nBestand: {item['stock']} → {after}\nVon: {interaction.user.mention}")


class InventoryView(discord.ui.View):
    def __init__(self, module, guild_id, user_id):
        super().__init__(timeout=300)
        self.module, self.guild_id, self.user_id = module, guild_id, user_id
        self.selected_item, self.selected_action = None, None
        with connect() as db:
            rows = db.execute("SELECT name,category,stock FROM trade_items WHERE guild_id=? ORDER BY name COLLATE NOCASE LIMIT 25", (guild_id,)).fetchall()
        self.add_item(InventoryItemSelect(rows))
        self.add_item(StockActionSelect())

    def make_embed(self):
        with connect() as db:
            rows = db.execute("SELECT name,category,stock FROM trade_items WHERE guild_id=? ORDER BY category COLLATE NOCASE,name COLLATE NOCASE LIMIT 25", (self.guild_id,)).fetchall()
            total = db.execute("SELECT COUNT(*) FROM trade_items WHERE guild_id=?", (self.guild_id,)).fetchone()[0]
        lines = [f"**{discord.utils.escape_markdown(r['name'])}** · {r['category']} — Bestand: **{r['stock']}**" for r in rows]
        embed = discord.Embed(title=f"📦 Zentrales Lager · {total} Artikel", description="\n".join(lines)[:3900] or "Noch keine Artikel. Nutze **+ Artikel hinzufügen**.", color=discord.Color.blurple())
        embed.set_footer(text="Artikel auswählen → Eingabe/Ausgabe wählen → Menge eingeben und speichern.")
        return embed

    @discord.ui.button(label="+ Artikel hinzufügen", style=discord.ButtonStyle.success, row=2)
    async def add_item_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Dieses Lagerfenster gehört zu einer anderen Person.", ephemeral=True)
        await interaction.response.send_modal(AddInventoryItemModal(self.module, self.guild_id, self.user_id))

    @discord.ui.button(label="Menge eingeben & speichern", style=discord.ButtonStyle.primary, row=2)
    async def save_movement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Dieses Lagerfenster gehört zu einer anderen Person.", ephemeral=True)
        if not self.selected_item or not self.selected_action:
            return await interaction.response.send_message("Bitte zuerst Artikel und Eingabe/Ausgabe auswählen.", ephemeral=True)
        await interaction.response.send_modal(StockMovementModal(self))


class InventoryItemSelect(discord.ui.Select):
    def __init__(self, rows):
        options = [discord.SelectOption(label=r["name"][:100], description=f"Bestand: {r['stock']}"[:100], value=r["name"]) for r in rows]
        super().__init__(placeholder="Artikel auswählen…", min_values=1, max_values=1, options=options or [discord.SelectOption(label="Noch keine Artikel", value="__none__")], disabled=not bool(rows), row=0)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            return await interaction.response.send_message("Dieses Lagerfenster gehört zu einer anderen Person.", ephemeral=True)
        view.selected_item = self.values[0]
        await interaction.response.send_message(f"Ausgewählt: **{discord.utils.escape_markdown(view.selected_item)}**", ephemeral=True)


class StockActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Eingabe oder Ausgabe auswählen…", min_values=1, max_values=1, options=[discord.SelectOption(label="Eingabe (ins Lager)", value="EINGANG", emoji="📥"), discord.SelectOption(label="Ausgabe (aus dem Lager)", value="AUSGANG", emoji="📤")], row=1)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            return await interaction.response.send_message("Dieses Lagerfenster gehört zu einer anderen Person.", ephemeral=True)
        view.selected_action = self.values[0]
        await interaction.response.send_message(f"Aktion ausgewählt: {'Eingabe' if self.values[0] == 'EINGANG' else 'Ausgabe'}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeModule(bot))
