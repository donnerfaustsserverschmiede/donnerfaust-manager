"""Wirtschaft & Handel: Lager, Preise, Handel und Kassenbuch."""
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import discord
from discord import app_commands
from discord.ext import commands
from app.core.database import DB_PATH

log = logging.getLogger(__name__)


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


class TradeModule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

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
    @app_commands.checks.has_permissions(manage_guild=True)
    async def artikel_anlegen(self, interaction: discord.Interaction, name: str, kategorie: str = "Sonstiges",
                              verkaufspreis: app_commands.Range[float, 0, 100000000] = 0,
                              einkaufspreis: app_commands.Range[float, 0, 100000000] = 0):
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

    @app_commands.command(name="lagerbestand", description="Zeigt den vollständigen Bestand, optional gefiltert.")
    async def lagerbestand(self, interaction: discord.Interaction, suche: str = "",
                           seite: app_commands.Range[int, 1, 1000] = 1):
        if not interaction.guild:
            return await interaction.response.send_message("Nur auf einem Server nutzbar.", ephemeral=True)
        with connect() as db:
            rows = db.execute("""SELECT name,category,stock,sell_price,buy_price FROM trade_items
                WHERE guild_id=? AND (?='' OR name LIKE ? OR category LIKE ?)
                ORDER BY category COLLATE NOCASE,name COLLATE NOCASE""",
                (interaction.guild.id, suche, f"%{suche}%", f"%{suche}%")).fetchall()
        if not rows:
            return await interaction.response.send_message("Keine Artikel gefunden. Nutze /artikel_anlegen, um Artikel einzurichten.", ephemeral=True)
        pages = max(1, (len(rows)+19)//20)
        if seite > pages:
            return await interaction.response.send_message(f"Es gibt {pages} Seite(n).", ephemeral=True)
        lines = [f"**{discord.utils.escape_markdown(r['name'])}** · {r['category']}\nBestand: **{r['stock']:,}** · Verkauf: {fmt(r['sell_price'])} · Einkauf: {fmt(r['buy_price'])}".replace(",", ".") for r in rows[(seite-1)*20:seite*20]]
        embed = discord.Embed(title=f"📦 Zentrales Lager · {len(rows)} Artikel",
            description="\n\n".join(lines)[:4000], color=discord.Color.blurple())
        embed.set_footer(text=f"Seite {seite}/{pages} · Filter: {suche or 'keiner'}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
        await self.send_log(interaction, "Lagerbewegung", f"Artikel: {item['name']}\nÄnderung: {delta*menge:+}\nBestand: {item['stock']} → {after}\nVon: {interaction.user.mention}\nNotiz: {notiz or '–'}")

    @app_commands.command(name="einlagern", description="Bucht Ressourcen ins Lager.")
    async def einlagern(self, interaction: discord.Interaction, artikel: str,
                        menge: app_commands.Range[int, 1, 100000000], notiz: str = ""):
        await self.change_stock(interaction, artikel, menge, 1, notiz)

    @app_commands.command(name="auslagern", description="Bucht Ressourcen aus dem Lager aus.")
    async def auslagern(self, interaction: discord.Interaction, artikel: str,
                        menge: app_commands.Range[int, 1, 100000000], notiz: str = ""):
        await self.change_stock(interaction, artikel, menge, -1, notiz)

    @app_commands.command(name="preis_setzen", description="Setzt Verkaufspreis und optional Einkaufspreis.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def preis_setzen(self, interaction: discord.Interaction, artikel: str,
                           verkaufspreis: app_commands.Range[float, 0, 100000000],
                           einkaufspreis: app_commands.Range[float, 0, 100000000] | None = None):
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
                unit = cash(einzelpreis if einzelpreis is not None else (item["sell_price"] if kind == "VERKAUF" else item["buy_price"]))
                if unit <= 0:
                    return await interaction.response.send_message("Bitte zuerst einen Preis größer 0 eintragen.", ephemeral=True)
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

    @app_commands.command(name="verkauf", description="Verkauft Waren, reduziert Lager und bucht Einnahmen.")
    async def verkauf(self, interaction: discord.Interaction, artikel: str,
                      menge: app_commands.Range[int, 1, 100000000], kunde: str,
                      einzelpreis: app_commands.Range[float, 0, 100000000] | None = None):
        await self.trade(interaction, artikel, menge, kunde, einzelpreis, "VERKAUF")

    @app_commands.command(name="einkauf", description="Kauft Waren ein, erhöht Lager und bucht Ausgaben.")
    async def einkauf(self, interaction: discord.Interaction, artikel: str,
                      menge: app_commands.Range[int, 1, 100000000], lieferant: str,
                      einzelpreis: app_commands.Range[float, 0, 100000000] | None = None):
        await self.trade(interaction, artikel, menge, lieferant, einzelpreis, "EINKAUF")

    @app_commands.command(name="startkapital", description="Erfasst das vorhandene Startkapital einmalig im Kassenbuch.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def startkapital(self, interaction: discord.Interaction, betrag: app_commands.Range[float, 0.01, 100000000], notiz: str = "Anfangsbestand"):
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
                                betrag: app_commands.Range[float, 0.01, 100000000],
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


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeModule(bot))
