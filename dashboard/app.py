"""Discord OAuth dashboard for Donnerfaust Manager."""
import asyncio
import logging
import hmac
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.database import get_guild_config, set_guild_setting, ALLOWED_SETTINGS
from bot import DonnerfaustBot

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1559529951303041054").strip()
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(48)

DB_PATH = Path(os.getenv("DASHBOARD_DB_PATH", "data/donnerfaust_manager.sqlite3"))
app = FastAPI(title="Donnerfaust Manager Dashboard")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=BASE_URL.startswith("https://"))

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8
INVITE_PERMISSIONS = 1099780189334

log = logging.getLogger("donnerfaust_manager.dashboard")
bot_instance = None
bot_task = None


@app.on_event("startup")
async def start_discord_bot():
    """Run the Discord bot alongside the dashboard in this single Render service."""
    global bot_instance, bot_task
    if not BOT_TOKEN:
        log.error("DISCORD_TOKEN fehlt: Dashboard startet, Discord-Bot bleibt aus.")
        return
    bot_instance = DonnerfaustBot()
    bot_task = asyncio.create_task(bot_instance.start(BOT_TOKEN), name="donnerfaust-discord-bot")
    await asyncio.sleep(0)
    log.info("Discord-Bot wird im Hintergrund gestartet.")


@app.on_event("shutdown")
async def stop_discord_bot():
    global bot_instance, bot_task
    if bot_instance and not bot_instance.is_closed():
        await bot_instance.close()
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass



def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_accounts():
    with db_connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS web_accounts (
            discord_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            global_name TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


def upsert_account(user: dict[str, Any]):
    init_accounts()
    with db_connect() as conn:
        conn.execute("""INSERT INTO web_accounts (discord_id, username, global_name, avatar)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
            username=excluded.username, global_name=excluded.global_name,
            avatar=excluded.avatar, last_login=CURRENT_TIMESTAMP""",
            (str(user["id"]), user.get("username", "Discord"),
             user.get("global_name") or "", user.get("avatar") or ""))


def page(title: str, body: str, user: dict[str, Any] | None = None) -> str:
    user_html = ""
    if user:
        avatar_hash = user.get("avatar")
        if avatar_hash:
            extension = "gif" if str(avatar_hash).startswith("a_") else "png"
            avatar_url = f'https://cdn.discordapp.com/avatars/{esc(user["id"])}/{esc(avatar_hash)}.{extension}?size=128'
        else:
            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
        user_html = f'<a class="profile-avatar" href="/profile" aria-label="Mein Konto" title="Mein Konto"><img class="avatar" src="{avatar_url}" alt="Discord-Profilbild"></a>'
    if not user:
        body = """<section class="login-screen"><div class="login-brand">⚡ DONNERFAUST <b>MANAGER</b></div><div class="login-mark">DF</div><h1>Willkommen</h1><p>Melde dich mit Discord an, um den Donnerfaust Manager zu betreten.</p><a class="button discord login-button" href="/login">Mit Discord anmelden</a></section>"""
    sidebar_html = ""
    if user:
        sidebar_html = """<aside class="dashboard-sidebar"><div class="sidebar-server"><span class="server-dot">DF</span><span>Donnerfaust Manager<small>Dashboard</small></span></div><div class="sidebar-label">ÜBERSICHT</div><a class="side-link" href="/">⌂ <span>Startseite</span></a><a class="side-link" href="/servers">▦ <span>Server auswählen</span></a><div class="sidebar-label">BOT-FUNKTIONEN</div><a class="side-link" href="/features/logging">◷ <span>Logging</span></a><a class="side-link" href="/features/tickets">▤ <span>Ticketsystem</span></a><a class="side-link" href="/features/moderation">♢ <span>Moderation</span></a><div class="sidebar-bottom"><a class="side-link" href="/profile">◉ <span>Mein Konto</span></a><a class="side-link" href="/logout">↪ <span>Abmelden</span></a></div></aside>"""
    header = ""
    if user:
        header = f'<header><details class="menu" id="main-menu"><summary aria-label="Menü öffnen">☰</summary><div class="menu-panel"><div class="menu-head"><span class="brand">⚡ DONNERFAUST <b>MANAGER</b></span><button type="button" class="menu-close" onclick="document.getElementById(\'main-menu\').open=false" aria-label="Menü schließen">×</button></div><nav><a href="/">Startseite <span>›</span></a><a href="/features/tickets">Ticketsystem <span>›</span></a><a href="/features/moderation">Moderation <span>›</span></a><a href="/features/logging">Logging <span>›</span></a><a href="/features/game-logging">Game-Logging <span>›</span></a><a href="/servers">Meine Server <span>›</span></a></nav><div class="menu-bottom"><a href="/profile">Mein Konto</a><a href="/logout">Abmelden</a></div></div></details><div class="brand">⚡ DONNERFAUST <b>MANAGER</b></div><div class="header-spacer"></div>{user_html}</header>'
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Donnerfaust Manager</title><style>
:root{{--bg:#f3f5f9;--panel:#ffffff;--gold:#e3b84d;--blue:#5865f2;--text:#202938;--muted:#687589;--line:#e1e6ef;--navy:#101b2d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,-apple-system,sans-serif;min-height:100vh}}
header{{display:flex;align-items:center;gap:14px;padding:12px 22px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:15;min-height:72px;box-shadow:0 2px 10px #17233a08}}
.brand{{font-weight:850;letter-spacing:.04em}}.brand b{{color:var(--gold)}}.header-spacer{{flex:1}}.dashboard-sidebar{{position:fixed;top:72px;bottom:0;left:0;width:248px;background:var(--navy);color:#e8edf5;padding:18px 13px;display:flex;flex-direction:column;z-index:10;overflow-y:auto}}.sidebar-server{{display:flex;align-items:center;gap:10px;padding:10px 9px 20px;border-bottom:1px solid #ffffff1a;font-weight:750;font-size:13px}}.sidebar-server small{{display:block;color:#9aa8bd;font-size:11px;font-weight:500;margin-top:3px}}.server-dot{{display:grid;place-items:center;width:38px;height:38px;background:var(--gold);color:#172033;border-radius:10px;font-weight:900}}.sidebar-label{{font-size:10px;letter-spacing:.12em;color:#8e9bb0;font-weight:800;margin:22px 10px 8px}}.side-link{{display:flex;align-items:center;gap:12px;padding:12px 11px;border-radius:8px;text-decoration:none;color:#d3dbea;font-size:14px;font-weight:600;margin:2px 0}}.side-link:hover{{background:#ffffff12;color:#fff}}.side-link:first-letter{{color:var(--gold)}}.sidebar-bottom{{margin-top:auto;border-top:1px solid #ffffff1a;padding-top:12px}}.profile-avatar{{display:flex;width:44px;height:44px;border-radius:50%;border:2px solid var(--gold);overflow:hidden;flex-shrink:0}}.profile-avatar .avatar{{width:100%;height:100%;object-fit:cover}}
main{{max-width:1180px;margin:28px auto;padding:0 24px 60px}}h1{{font-size:clamp(27px,4vw,36px);margin:8px 0 14px;letter-spacing:-.025em}}h2{{font-size:19px;margin:0 0 12px}}p{{color:var(--muted);line-height:1.65}}a{{color:var(--blue)}}.button,button{{display:inline-block;border:0;border-radius:9px;padding:12px 16px;background:var(--gold);color:#172033;font-weight:750;text-decoration:none;cursor:pointer;font-size:14px}}.secondary{{background:var(--blue);color:white}}.discord{{background:#5865f2;color:white}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:16px;margin-top:20px}}.card{{border:1px solid var(--line);border-radius:13px;padding:22px;background:#fff;box-shadow:0 3px 12px #15233a08}}.tag{{font-size:12px;color:var(--gold);text-transform:uppercase;letter-spacing:.1em}}.row{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0}}label{{display:block;margin:14px 0 6px;font-weight:650}}select,input[type=text],textarea{{width:100%;padding:12px;border:1px solid #d5dce7;border-radius:8px;background:#fff;color:var(--text);font:inherit}}input[type=checkbox]{{width:19px;height:19px;accent-color:var(--gold)}}.check{{display:flex;align-items:center;gap:10px;margin:12px 0;color:var(--muted)}}.notice{{padding:12px 14px;border-radius:9px;background:#eef2ff;color:#33415b;margin:14px 0}}.error{{border-left:4px solid #d36b76}}.guild-icon{{width:44px;height:44px;border-radius:12px;background:#edf0ff;color:var(--blue);display:grid;place-items:center;font-weight:800;font-size:20px}}.guild{{display:flex;align-items:center;gap:12px;margin-bottom:15px}}.spacer{{height:8px}}.user{{order:3;display:flex;align-items:center;gap:10px;color:var(--muted);font-size:14px}}.user .avatar{{width:44px;height:44px;border-radius:50%;border:2px solid var(--gold);object-fit:cover}}.user a{{display:none}}.menu{{position:relative;order:0;flex-shrink:0;display:none}}.menu>summary{{list-style:none;cursor:pointer;border:1px solid var(--line);border-radius:10px;width:46px;height:46px;display:grid;place-items:center;font-size:27px;line-height:1}}.menu>summary::-webkit-details-marker{{display:none}}.menu[open] .menu-panel{{position:fixed;inset:0 auto 0 0;width:min(50vw,520px);min-width:300px;height:100dvh;z-index:30;background:linear-gradient(160deg,#112641,#081426);border-right:1px solid var(--line);box-shadow:20px 0 70px #0008;display:flex;flex-direction:column;padding:22px clamp(20px,4vw,38px);overflow-y:auto}}.menu-head{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding-bottom:24px;border-bottom:1px solid var(--line)}}.menu-close{{background:transparent;color:var(--text);font-size:30px;padding:0 8px}}.menu nav{{display:flex;flex-direction:column;margin:22px 0;gap:4px}}.menu nav a{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 12px;border-radius:10px;text-decoration:none;color:#e8edf5;font-size:clamp(17px,2vw,21px)}}.menu nav a:hover{{background:#20334c}}.menu nav a span{{color:var(--gold);font-size:24px}}.menu-bottom{{display:flex;flex-direction:column;gap:14px;margin-top:auto;padding-top:20px;border-top:1px solid var(--line)}}.menu-bottom a{{text-decoration:none}}.login-screen{{min-height:calc(100dvh - 40px);max-width:100%;margin:0 auto;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:28px 22px}}body:has(.login-screen){{background:radial-gradient(ellipse at 50% 30%,#142b4a 0,#081426 65%)}}body:has(.login-screen) main{{min-height:100dvh;display:flex;flex-direction:column;justify-content:center;margin:0 auto;padding:20px;width:100%;max-width:560px}}body:has(.login-screen) header{{display:none}}body:has(.login-screen) footer{{display:none}}.login-brand{{font-size:clamp(19px,4vw,24px);font-weight:850;white-space:nowrap;letter-spacing:.03em}}.login-brand b{{color:var(--gold)}}.login-mark{{display:grid;place-items:center;margin:34px auto 24px;width:82px;height:82px;border:2px solid var(--gold);border-radius:50%;font-size:26px;font-weight:900;color:var(--gold);box-shadow:0 0 38px #e3b84d22}}.login-screen h1{{font-size:clamp(27px,5vw,34px);margin:0 0 10px}}.login-screen p{{max-width:340px;margin:0 auto;color:var(--muted)}}.login-button{{display:block;margin-top:28px;padding:16px 22px;min-width:min(100%,280px)}}footer{{color:#71819a;font-size:12px;margin-top:32px}}@media(max-width:600px){{header{{align-items:center;gap:10px;padding-left:12px;padding-right:12px}}.user span{{display:none}}.user .avatar{{width:40px;height:40px}}.menu[open] .menu-panel{{width:min(88vw,390px);min-width:0;padding:18px 20px}}.menu nav a{{font-size:19px;padding:14px 10px}}main{{margin-top:20px}}}}
</style></head><body>{header}{sidebar_html}<main>{body}<footer>Donnerfaust Manager · Discord-Anmeldung · Einstellungen je Server</footer></main></body></html>"""


def esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def current_user(request: Request) -> dict[str, Any] | None:
    return request.session.get("user")


def authorized_guilds(guilds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for guild in guilds:
        try:
            permissions = int(guild.get("permissions", "0"))
        except (TypeError, ValueError):
            continue
        if permissions & (MANAGE_GUILD | ADMINISTRATOR):
            result.append(guild)
    return result


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = current_user(request)
    if not user:
        body = """<section class="card"><div class="tag">Donnerfaust Interactive · Discord Bot</div><h1>Dein Discord. Deine Regeln.</h1>
<p>Der Donnerfaust Manager bringt die wichtigsten Server-Werkzeuge an einen Ort. Melde dich mit Discord an, um die Website zu betreten und mehr über Logging, Tickets und Moderation zu erfahren.</p>
<div class="row"><a class="button discord" href="/login">🎮 Mit Discord anmelden</a></div>
<div class="notice">Die Anmeldung erstellt beim ersten erfolgreichen Login automatisch dein Webseitenprofil. Ein separates Webseitenpasswort brauchst du nicht.</div></section>
<div class="grid"><section class="card"><div class="tag">01 · Logging</div><h2>Protokolle</h2><p>Behalte wichtige Serverereignisse an einem zentralen Ort im Blick.</p><a href="/features/logging">Mehr erfahren →</a></section><section class="card"><div class="tag">02 · Ticketsystem</div><h2>Support-Center</h2><p>Strukturiere Support-Anfragen mit einem übersichtlichen Ticketsystem.</p><a href="/features/tickets">Mehr erfahren →</a></section><section class="card"><div class="tag">03 · Moderation</div><h2>Server-Schutz</h2><p>Werkzeuge für eine geordnete und verantwortungsvolle Servermoderation.</p><a href="/features/moderation">Mehr erfahren →</a></section></div>"""
        return page("Startseite", body)
    display = user.get("global_name") or user.get("username", "Discord")
    body = f"""<div class="tag">Persönlicher Bereich</div><h1>Willkommen, {esc(display)}!</h1><p>Du bist mit Discord angemeldet. Wähle eine Funktion im Menü, um mehr zu erfahren, oder öffne die Serververwaltung, wenn du entsprechende Rechte besitzt.</p>
<div class="grid"><section class="card"><div class="tag">01 · Logging</div><h2>Logging</h2><p>Protokollkanäle und Ereignisse konfigurieren.</p><a class="button secondary" href="/features/logging">Logging öffnen</a></section><section class="card"><div class="tag">02 · Ticketsystem</div><h2>Ticketsystem</h2><p>Support-Einstellungen und Ticket-Abläufe.</p><a class="button secondary" href="/features/tickets">Tickets öffnen</a></section><section class="card"><div class="tag">03 · Moderation</div><h2>Moderation</h2><p>Moderationswerkzeuge und Schutzfunktionen.</p><a class="button secondary" href="/features/moderation">Moderation öffnen</a></section></div>
<div class="row"><a class="button" href="/servers">Meine Server verwalten</a></div>"""
    return page("Startseite", body, user)


@app.get("/login")
async def login(request: Request):
    if not CLIENT_SECRET:
        return HTMLResponse(page("Einrichtung nötig", '<h1>Einrichtung nötig</h1><div class="notice error">Für den Discord-Login fehlt DISCORD_CLIENT_SECRET in den Hosting-Umgebungsvariablen.</div>'), status_code=503)
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    query = urlencode({"client_id": CLIENT_ID, "redirect_uri": BASE_URL + "/callback", "response_type": "code", "scope": "identify guilds", "state": state, "prompt": "consent"})
    return RedirectResponse("https://discord.com/oauth2/authorize?" + query, status_code=302)


@app.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        raise HTTPException(status_code=400, detail=f"Discord-OAuth wurde abgebrochen oder abgelehnt: {error}. Bitte prüfe die OAuth2-Redirect-URL in Discord Developer Portal.")
    expected = request.session.pop("oauth_state", "")
    if not code or not expected or not hmac.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Anmeldung abgelaufen oder ungültig. Bitte erneut versuchen.")
    if not CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Discord OAuth Client Secret fehlt.")
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post("https://discord.com/api/oauth2/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
            "code": code, "redirect_uri": BASE_URL + "/callback",
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if token_response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Discord konnte die Anmeldung nicht abschließen. OAuth-Einstellungen prüfen.")
        token = token_response.json()["access_token"]
        user_response = await client.get(DISCORD_API + "/users/@me", headers={"Authorization": f"Bearer {token}"})
        guild_response = await client.get(DISCORD_API + "/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        user_response.raise_for_status()
        guild_response.raise_for_status()
        user_data = user_response.json()
        upsert_account(user_data)
        request.session.clear()
        request.session["user"] = user_data
        request.session["guilds"] = authorized_guilds(guild_response.json())
        request.session["csrf"] = secrets.token_urlsafe(32)
    return RedirectResponse("/", status_code=303)


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    display = user.get("global_name") or user.get("username", "Discord")
    avatar_hash = user.get("avatar")
    if avatar_hash:
        extension = "gif" if str(avatar_hash).startswith("a_") else "png"
        avatar_url = f'https://cdn.discordapp.com/avatars/{esc(user["id"])}/{esc(avatar_hash)}.{extension}?size=256'
    else:
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
    discord_user_id = user["id"]
    csrf_token = request.session.get("csrf", "")
    body = f"""<section class="card"><div class="tag">Mein Konto</div><img src="{avatar_url}" alt="Discord-Profilbild" style="width:96px;height:96px;border-radius:50%;border:3px solid var(--gold);object-fit:cover"><h1>{esc(display)}</h1><p>Dein Name und Profilbild werden von Discord übernommen. Änderungen daran nimmst du direkt in Discord vor.</p><a class="button secondary" href="https://discord.com/users/{esc(discord_user_id)}" target="_blank" rel="noopener">Discord-Profil öffnen</a><div class="notice">Du kannst dein Webseitenkonto hier löschen. Dein Discord-Konto bleibt dabei bestehen.</div><form method="post" action="/profile/delete" onsubmit="return confirm('Webseitenkonto wirklich löschen?')"><input type="hidden" name="csrf" value="{esc(csrf_token)}"><button type="submit">Webseitenkonto löschen</button></form></section>"""
    return page("Mein Konto", body, user)


@app.post("/profile/delete")
async def delete_profile(request: Request, csrf: str = Form("")):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    expected = request.session.get("csrf", "")
    if not expected or not hmac.compare_digest(expected, csrf):
        raise HTTPException(status_code=403, detail="Sicherheitsprüfung fehlgeschlagen. Bitte Seite neu laden.")
    with db_connect() as conn:
        conn.execute("DELETE FROM web_accounts WHERE discord_id=?", (str(user["id"]),))
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/invite")
async def invite():
    query = urlencode({"client_id": CLIENT_ID, "permissions": str(INVITE_PERMISSIONS), "integration_type": "0", "scope": "bot applications.commands"})
    return RedirectResponse("https://discord.com/oauth2/authorize?" + query, status_code=302)


@app.get("/servers", response_class=HTMLResponse)
async def servers(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    guilds = request.session.get("guilds", [])
    body = '<div class="tag">Serververwaltung</div><h1>Meine Server</h1><p>Nur Server, auf denen dein Discord-Konto „Server verwalten“ oder Administrator besitzt, werden hier angezeigt.</p><div class="grid">'
    for guild in guilds:
        name = esc(guild.get("name", "Discord-Server"))
        icon = esc((guild.get("name") or "?")[:1].upper())
        body += f'<section class="card"><div class="guild"><div class="guild-icon">{icon}</div><h2>{name}</h2></div><a class="button secondary" href="/servers/{esc(guild["id"])}">Einstellungen öffnen</a></section>'
    body += '</div><div class="row"><a class="button discord" href="/invite">Bot einladen</a></div>'
    if not guilds:
        body += '<div class="notice">Dein Konto hat keine Server mit den erforderlichen Verwaltungsrechten gefunden.</div>'
    return page("Meine Server", body, user)


@app.get("/features/{feature}", response_class=HTMLResponse)
async def feature_page(request: Request, feature: str):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    pages = {
        "logging": ("Logging", "Serverereignisse protokollieren", "Wähle später pro Server den Protokollkanal und die Ereignisse, die dein Bot erfassen soll."),
        "tickets": ("Ticketsystem", "Support übersichtlich organisieren", "Konfiguriere später Ticket-Kategorien, Support-Rollen, Begrüßungen und dein Ticket-Panel."),
        "moderation": ("Moderation", "Werkzeuge für dein Moderationsteam", "Verwalte später Timeout, Kick, Ban und das Bereinigen von Nachrichten."),
        "game-logging": ("Game-Logging", "Spiele mit Discord verbinden", "Verbinde unterstützte Gameserver später über sichere Schnittstellen, um Spielereignisse in Discord zu protokollieren."),
    }
    selected = pages.get(feature)
    if not selected:
        raise HTTPException(status_code=404, detail="Diese Funktionsseite gibt es nicht.")
    title, subtitle, description = selected
    body = f'<div class="tag">Bot-Funktion</div><h1>{esc(title)}</h1><section class="card"><h2>{esc(subtitle)}</h2><p>{esc(description)}</p><div class="notice">Diese Funktionsseite ist angelegt. Die einzelnen Einstellmöglichkeiten werden schrittweise angebunden.</div><a class="button secondary" href="/servers">Zur Serververwaltung</a></section>'
    return page(title, body, user)


@app.get("/servers/{guild_id}", response_class=HTMLResponse)
async def server_settings(request: Request, guild_id: str, saved: int = 0):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    guild = next((g for g in request.session.get("guilds", []) if g.get("id") == guild_id), None)
    if not guild:
        raise HTTPException(status_code=403, detail="Du darfst diesen Server nicht verwalten. Bitte melde dich neu an.")
    config = get_guild_config(int(guild_id))
    channels = []
    if BOT_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(f"{DISCORD_API}/guilds/{guild_id}/channels", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if response.status_code == 200:
                    channels = response.json()
        except Exception:
            channels = []
    text_channels = [c for c in channels if c.get("type") == 0]
    category_channels = [c for c in channels if c.get("type") == 4]
    options = '<option value="">— Kanal auswählen —</option>'
    for channel in text_channels:
        selected = " selected" if config.get("log_channel_id") == int(channel["id"]) else ""
        options += f'<option value="{esc(channel["id"])}"{selected}>#{esc(channel["name"])}</option>'
    ticket_panel_options = '<option value="">— Ticket-Panel-Kanal auswählen —</option>'
    for channel in text_channels:
        selected = " selected" if config.get("ticket_panel_channel_id") == int(channel["id"]) else ""
        ticket_panel_options += f'<option value="{esc(channel["id"])}"{selected}>#{esc(channel["name"])}</option>'
    category_options = '<option value="">— Kategorie automatisch erstellen —</option>'
    for channel in category_channels:
        selected = " selected" if config.get("ticket_category_id") == int(channel["id"]) else ""
        category_options += f'<option value="{esc(channel["id"])}"{selected}>{esc(channel["name"])}</option>'
    roles = []
    if BOT_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                role_response = await client.get(f"{DISCORD_API}/guilds/{guild_id}/roles", headers={"Authorization": f"Bot {BOT_TOKEN}"})
                if role_response.status_code == 200:
                    roles = role_response.json()
        except Exception:
            roles = []
    role_options = '<option value="">— Support-Rolle auswählen —</option>'
    for role in roles:
        if role.get("name") == "@everyone":
            continue
        selected = " selected" if config.get("ticket_support_role_id") == int(role["id"]) else ""
        role_options += f'<option value="{esc(role["id"])}"{selected}>{esc(role["name"])}</option>'
    checkboxes = [
        ("logging_message_delete", "Gelöschte Nachrichten protokollieren", True),
        ("logging_message_edit", "Bearbeitete Nachrichten protokollieren", True),
        ("logging_member_join", "Mitgliederbeitritte protokollieren", True),
        ("logging_member_leave", "Mitgliederaustritte protokollieren", True),
        ("logging_channel_events", "Kanaländerungen protokollieren", True),
        ("logging_role_events", "Rollenänderungen protokollieren", True),
        ("logging_voice_events", "Sprachkanalwechsel protokollieren", False),
        ("moderation_timeout_enabled", "Timeout-Befehl aktivieren", True),
        ("moderation_kick_enabled", "Kick-Befehl aktivieren", True),
        ("moderation_ban_enabled", "Ban-Befehl aktivieren", True),
        ("moderation_clear_enabled", "Nachrichten bereinigen aktivieren", True),
        ("antispam_enabled", "Anti-Spam aktivieren (7 Nachrichten in 8 Sekunden = 1 Minute Timeout)", False),
    ]
    checks = ""
    for key, label, default in checkboxes:
        val = config.get(key, default)
        checked = " checked" if val is True or val == "true" else ""
        checks += f'<label class="check"><input type="checkbox" name="{key}" value="true"{checked}>{esc(label)}</label>'
    welcome = esc(config.get("ticket_welcome_message", "Hallo! Beschreibe bitte dein Anliegen."))
    body = f'<div class="row"><div><div class="tag">Servereinstellungen</div><h1>{esc(guild.get("name","Discord-Server"))}</h1></div><a href="/servers" class="button secondary">← Meine Server</a></div>'
    if saved:
        body += '<div class="notice">Einstellungen gespeichert.</div>'
    body += f"""<form method="post" action="/servers/{esc(guild_id)}/save"><input type="hidden" name="csrf" value="{esc(request.session.get("csrf",""))}">
<section class="card"><div class="tag">Schublade 01</div><h2>Logging</h2><p>Wähle den Kanal für die Ereignisprotokolle. Der Bot benötigt dort Kanal ansehen, Nachrichten senden und Links einbetten.</p><label for="log_channel_id">Protokollkanal</label><select id="log_channel_id" name="log_channel_id">{options}</select>{checks}</section>
<div class="spacer"></div><section class="card"><div class="tag">Schublade 02</div><h2>Ticketsystem</h2><p>Diese Einstellungen werden beim Erstellen neuer Tickets direkt vom Bot verwendet. Die Rollen- und Kanallisten werden über deinen Discord-Bot geladen.</p><label for="ticket_panel_channel_id">Kanal für das Ticket-Panel</label><select id="ticket_panel_channel_id" name="ticket_panel_channel_id">{ticket_panel_options}</select><label for="ticket_category_id">Ticket-Kategorie</label><select id="ticket_category_id" name="ticket_category_id">{category_options}</select><label for="ticket_support_role_id">Support-Rolle</label><select id="ticket_support_role_id" name="ticket_support_role_id">{role_options}</select><label for="ticket_welcome_message">Begrüßung im Ticket</label><textarea id="ticket_welcome_message" name="ticket_welcome_message" rows="3">{welcome}</textarea></section>
<div class="spacer"></div><section class="card"><div class="tag">Schublade 03</div><h2>Moderation</h2><p>Die Schalter oben werden vom Bot ausgewertet. Moderationsbefehle benötigen zusätzlich die passenden Discord-Rechte für das ausführende Team und den Bot.</p></section>
<div class="row"><button type="submit">Einstellungen speichern</button></div></form>"""
    return page("Servereinstellungen", body, user)


@app.post("/servers/{guild_id}/save")
async def save_settings(request: Request, guild_id: str, csrf: str = Form(""), log_channel_id: str = Form(""), ticket_panel_channel_id: str = Form(""), ticket_category_id: str = Form(""), ticket_support_role_id: str = Form(""), ticket_welcome_message: str = Form("Hallo! Beschreibe bitte dein Anliegen.")):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    guild = next((g for g in request.session.get("guilds", []) if g.get("id") == guild_id), None)
    if not guild:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diesen Server.")
    expected = request.session.get("csrf", "")
    if not expected or not hmac.compare_digest(expected, csrf):
        raise HTTPException(status_code=403, detail="Sicherheitsprüfung fehlgeschlagen. Seite neu laden.")
    for key, value in (("log_channel_id", log_channel_id), ("ticket_panel_channel_id", ticket_panel_channel_id), ("ticket_category_id", ticket_category_id), ("ticket_support_role_id", ticket_support_role_id)):
        if value:
            if not value.isdigit():
                raise HTTPException(status_code=422, detail="Ungültige Kanal- oder Rollen-ID.")
            set_guild_setting(int(guild_id), key, int(value))
        elif key != "log_channel_id":
            set_guild_setting(int(guild_id), key, "")
    set_guild_setting(int(guild_id), "ticket_welcome_message", ticket_welcome_message[:1500])
    form = await request.form()
    checkbox_keys = [key for key in ALLOWED_SETTINGS if key.startswith("logging_") or key.startswith("moderation_") or key == "antispam_enabled"]
    for key in checkbox_keys:
        set_guild_setting(int(guild_id), key, form.get(key) == "true")
    return RedirectResponse(f"/servers/{guild_id}?saved=1", status_code=303)
