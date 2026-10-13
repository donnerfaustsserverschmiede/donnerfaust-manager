"""Dashboard web app: Discord OAuth login and per-guild settings.

Run with: uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
Never expose the bot token or OAuth client secret to the browser.
"""
import hmac
import os
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.database import get_guild_config, set_guild_setting, ALLOWED_SETTINGS

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1559529951303041054").strip()
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()
if not SESSION_SECRET:
    # Safe for local development only. Set SESSION_SECRET in the deployment environment.
    SESSION_SECRET = secrets.token_urlsafe(48)

app = FastAPI(title="Donnerfaust Manager Dashboard")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=BASE_URL.startswith("https://"))

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8
INVITE_PERMISSIONS = 1099780189334


def page(title: str, body: str, user: dict[str, Any] | None = None) -> str:
    user_html = ""
    if user:
        avatar = ""
        if user.get("avatar"):
            avatar = f'<img class="avatar" src="https://cdn.discordapp.com/avatars/{user["id"]}/{user["avatar"]}.png?size=64" alt="">'
        user_html = f'<div class="user">{avatar}<span>{esc(user.get("global_name") or user.get("username","Discord"))}</span><a href="/logout">Abmelden</a></div>'
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Donnerfaust Manager</title><style>
:root{{--bg:#081426;--panel:#101f35;--panel2:#142944;--gold:#e3b84d;--blue:#4c83d8;--text:#f4f6fb;--muted:#aebbd0;--line:#2b3d57}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at top,#142b4a 0,#081426 55%);color:var(--text);font:16px system-ui,-apple-system,sans-serif;min-height:100vh}}
header{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px max(18px,calc((100vw - 1080px)/2));border-bottom:1px solid var(--line);background:#081426dd;position:sticky;top:0}}
.brand{{font-weight:800;letter-spacing:.04em}}.brand b{{color:var(--gold)}}.user{{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:14px}}.avatar{{width:32px;height:32px;border-radius:50%}}
main{{max-width:1080px;margin:30px auto;padding:0 18px 60px}}h1{{font-size:clamp(27px,4vw,40px);margin:8px 0}}h2{{font-size:20px;margin:0 0 12px}}p,.muted{{color:var(--muted);line-height:1.55}}a{{color:#a9cbff}}.button,button{{display:inline-block;border:0;border-radius:10px;padding:12px 16px;background:var(--gold);color:#172033;font-weight:750;text-decoration:none;cursor:pointer;font-size:15px}}.secondary{{background:var(--blue);color:white}}.danger{{background:#873d49;color:white}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin-top:20px}}.card{{border:1px solid var(--line);border-radius:16px;padding:20px;background:linear-gradient(145deg,#132742,#0d1b2e)}}.card p{{margin-top:0}}.tag{{font-size:12px;color:var(--gold);text-transform:uppercase;letter-spacing:.1em}}.row{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0}}label{{display:block;margin:14px 0 6px;font-weight:650}}select,input[type=text],textarea{{width:100%;padding:12px;border:1px solid var(--line);border-radius:9px;background:#081426;color:var(--text);font:inherit}}input[type=checkbox]{{width:19px;height:19px;accent-color:var(--gold)}}.check{{display:flex;align-items:center;gap:10px;margin:12px 0;color:var(--muted)}}.notice{{padding:12px 14px;border-radius:10px;background:#20334c;margin:14px 0}}.success{{border-left:4px solid #60c79b}}.error{{border-left:4px solid #d36b76}}.guild-icon{{width:44px;height:44px;border-radius:12px;background:#263c5a;display:grid;place-items:center;font-weight:800;font-size:20px}}.guild{{display:flex;align-items:center;gap:12px;margin-bottom:15px}}.spacer{{height:8px}}footer{{color:#71819a;font-size:12px;margin-top:32px}}@media(max-width:520px){{header{{align-items:flex-start}}.user span{{display:none}}main{{margin-top:20px}}}}
</style></head><body><header><div class="brand">⚡ DONNERFAUST <b>MANAGER</b></div>{user_html}</header><main>{body}<footer>Donnerfaust Manager · Dashboard-Vorschau · Einstellungen werden serverbezogen gespeichert.</footer></main></body></html>"""


def esc(value: Any) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def current_user(request: Request) -> dict[str, Any] | None:
    return request.session.get("user")


async def discord_get(path: str, token: str) -> Any:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(DISCORD_API + path, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return response.json()


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
async def home(request: Request) -> str:
    user = current_user(request)
    if not user:
        body = """<section class="card"><div class="tag">Ein Kontrollzentrum. Alle Module.</div><h1>Dein Discord. Deine Regeln.</h1>
<p>Verwalte Logging, Tickets und Moderation zentral über eine Website – mit einer eigenen Schublade für jede Funktion und getrennten Einstellungen für jeden Server.</p>
<div class="row"><a class="button" href="/login">Mit Discord anmelden</a><a class="button secondary" href="/invite">Bot einladen</a></div>
<div class="notice">Der Bot muss separat gehostet und gestartet werden, damit die Discord-Funktionen online ausgeführt werden.</div></section>
<div class="grid"><section class="card"><div class="tag">01 · Logging</div><h2>Protokolle</h2><p>Wähle einen Zielkanal und die Ereignisse, die protokolliert werden sollen.</p></section><section class="card"><div class="tag">02 · Tickets</div><h2>Support-Center</h2><p>Konfiguriere Ticket-Kategorien, Support-Rolle und Ticket-Panel.</p></section><section class="card"><div class="tag">03 · Moderation</div><h2>Server-Schutz</h2><p>Verwalte Moderationsfunktionen und deren Protokollierung.</p></section></div>"""
        return page("Start", body)
    guilds = request.session.get("guilds", [])
    body = f'<div class="tag">Dashboard</div><h1>Willkommen, {esc(user.get("global_name") or user.get("username","Admin"))}</h1><p>Wähle einen Server, den du verwalten darfst.</p><div class="grid">'
    for guild in guilds:
        icon = esc((guild.get("name") or "?")[:1].upper())
        body += f'<section class="card"><div class="guild"><div class="guild-icon">{icon}</div><div><h2>{esc(guild.get("name","Discord-Server"))}</h2><p style="margin:0">Server-ID: {esc(guild["id"])}</p></div></div><a class="button secondary" href="/servers/{esc(guild["id"])}">Einstellungen öffnen</a></section>'
    body += '</div><div class="row"><a class="button" href="/invite">＋ Bot einladen</a></div>'
    if not guilds:
        body += '<div class="notice">Es wurden keine Server gefunden, für die dein Discord-Konto die Berechtigung „Server verwalten“ besitzt.</div>'
    return page("Dashboard", body, user)


@app.get("/login")
async def login(request: Request):
    if not CLIENT_SECRET:
        return HTMLResponse(page("Einrichtung nötig", '<h1>Einrichtung nötig</h1><div class="notice error">Für den Discord-Login fehlt DISCORD_CLIENT_SECRET in den Hosting-Umgebungsvariablen. Bitte nicht im Quellcode eintragen.</div>'), status_code=503)
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    query = urlencode({"client_id": CLIENT_ID, "redirect_uri": BASE_URL + "/callback", "response_type": "code", "scope": "identify guilds", "state": state, "prompt": "consent"})
    return RedirectResponse("https://discord.com/oauth2/authorize?" + query, status_code=302)


@app.get("/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse("/?error=discord_login_cancelled", status_code=303)
    expected = request.session.pop("oauth_state", "")
    if not code or not expected or not hmac.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Ungültige oder abgelaufene Anmeldung. Bitte erneut versuchen.")
    if not CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Discord OAuth Client Secret fehlt in der Hosting-Konfiguration.")
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post("https://discord.com/api/oauth2/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
            "code": code, "redirect_uri": BASE_URL + "/callback",
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if token_response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Discord konnte die Anmeldung nicht abschließen. Redirect-URL und OAuth-Einstellungen prüfen.")
        token = token_response.json()["access_token"]
        user_response = await client.get(DISCORD_API + "/users/@me", headers={"Authorization": f"Bearer {token}"})
        guild_response = await client.get(DISCORD_API + "/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        user_response.raise_for_status()
        guild_response.raise_for_status()
        request.session.clear()
        request.session["user"] = user_response.json()
        request.session["guilds"] = authorized_guilds(guild_response.json())
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/invite")
async def invite():
    query = urlencode({"client_id": CLIENT_ID, "permissions": str(INVITE_PERMISSIONS), "integration_type": "0", "scope": "bot applications.commands"})
    return RedirectResponse("https://discord.com/oauth2/authorize?" + query, status_code=302)


@app.get("/servers/{guild_id}", response_class=HTMLResponse)
async def server_settings(request: Request, guild_id: str, saved: int = 0):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    guild = next((g for g in request.session.get("guilds", []) if g.get("id") == guild_id), None)
    if not guild:
        raise HTTPException(status_code=403, detail="Du darfst diesen Server nicht verwalten. Bitte melde dich neu an.")
    config = get_guild_config(int(guild_id))
    token = request.session.get("access_token")
    # Access tokens are intentionally not stored in a browser-visible page; get channels only when token is retained server-side.
    channels = []
    if token:
        try:
            channels = await discord_get(f"/guilds/{guild_id}/channels", token)
        except Exception:
            channels = []
    text_channels = [c for c in channels if c.get("type") == 0]
    options = '<option value="">— Kanal auswählen —</option>'
    for channel in text_channels:
        selected = " selected" if config.get("log_channel_id") == int(channel["id"]) else ""
        options += f'<option value="{esc(channel["id"])}"{selected}>#{esc(channel["name"])}</option>'
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
        ("antispam_enabled", "Anti-Spam aktivieren (in Entwicklung)", False),
    ]
    checks = ""
    for key, label, default in checkboxes:
        val = config.get(key, default)
        checked = " checked" if val is True or val == "true" else ""
        checks += f'<label class="check"><input type="checkbox" name="{key}" value="true"{checked}>{esc(label)}</label>'
    welcome = esc(config.get("ticket_welcome_message", "Hallo! Beschreibe bitte dein Anliegen."))
    body = f'<div class="row"><div><div class="tag">Servereinstellungen</div><h1>{esc(guild.get("name","Discord-Server"))}</h1></div><a href="/" class="button secondary">← Serverübersicht</a></div>'
    if saved:
        body += '<div class="notice success">Einstellungen gespeichert.</div>'
    body += f"""<form method="post" action="/servers/{esc(guild_id)}/save"><input type="hidden" name="csrf" value="{esc(request.session.get("csrf",""))}">
<section class="card"><div class="tag">Schublade 01</div><h2>Logging</h2><p>Wähle den Kanal für die Ereignisprotokolle. Der Bot benötigt dort Kanal ansehen, Nachrichten senden und Links einbetten.</p><label for="log_channel_id">Protokollkanal</label><select id="log_channel_id" name="log_channel_id">{options}</select>{checks}</section>
<div class="spacer"></div><section class="card"><div class="tag">Schublade 02</div><h2>Ticketsystem</h2><p>Die erweiterten Ticket-Einstellungen werden in einer nächsten Ausbaustufe an diese Konfiguration angebunden.</p><label for="ticket_welcome_message">Begrüßung im Ticket</label><textarea id="ticket_welcome_message" name="ticket_welcome_message" rows="3">{welcome}</textarea></section>
<div class="spacer"></div><section class="card"><div class="tag">Schublade 03</div><h2>Moderation</h2><p>Schalte die gewünschten Moderationsfunktionen ein oder aus. Die Schalter werden gespeichert; das Durchsetzen der Schalter im Bot wird als eigener Integrationsschritt ergänzt.</p></section>
<div class="row"><button type="submit">Einstellungen speichern</button></div></form>"""
    return page("Servereinstellungen", body, user)


@app.post("/servers/{guild_id}/save")
async def save_settings(request: Request, guild_id: str, csrf: str = Form(""), log_channel_id: str = Form(""), ticket_welcome_message: str = Form("Hallo! Beschreibe bitte dein Anliegen.")):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    guild = next((g for g in request.session.get("guilds", []) if g.get("id") == guild_id), None)
    if not guild:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diesen Server.")
    expected = request.session.get("csrf", "")
    if not expected or not hmac.compare_digest(expected, csrf):
        raise HTTPException(status_code=403, detail="Sicherheitsprüfung fehlgeschlagen. Seite neu laden.")
    if log_channel_id:
        if not log_channel_id.isdigit():
            raise HTTPException(status_code=422, detail="Ungültige Kanal-ID.")
        set_guild_setting(int(guild_id), "log_channel_id", int(log_channel_id))
    set_guild_setting(int(guild_id), "ticket_welcome_message", ticket_welcome_message[:1500])
    form = await request.form()
    checkbox_keys = [key for key in ALLOWED_SETTINGS if key.startswith("logging_") or key.startswith("moderation_") or key == "antispam_enabled"]
    for key in checkbox_keys:
        set_guild_setting(int(guild_id), key, form.get(key) == "true")
    return RedirectResponse(f"/servers/{guild_id}?saved=1", status_code=303)


@app.middleware("http")
async def set_csrf(request: Request, call_next):
    response = await call_next(request)
    if request.session.get("user") and not request.session.get("csrf"):
        request.session["csrf"] = secrets.token_urlsafe(32)
    return response
