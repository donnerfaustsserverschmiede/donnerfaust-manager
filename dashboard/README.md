# Donnerfaust Manager – Web-Dashboard

**Das Dashboard ist die zentrale Bedienoberfläche.** Serveradministratoren sollen Einstellungen nicht per Chatbefehl pflegen müssen. Der Bot bleibt der ausführende Dienst auf Discord.

## Geplante Nutzerführung
1. Auf der Website mit Discord OAuth2 anmelden.
2. Nur Discord-Server anzeigen, auf denen die Person die Berechtigung `MANAGE_GUILD` hat und für die sie verwalten darf.
3. Mit **„Bot einladen“** den Discord-OAuth2-Installationslink öffnen.
4. Einen Server auswählen und Funktionen über Formulare/Schalter konfigurieren.
5. Änderungen werden serverbezogen gespeichert und vom Bot gelesen.

## Dashboard-Module
- **Übersicht:** Bot-Status, Serverauswahl und Einrichtungshinweise.
- **Einladung:** Schaltfläche zum Einladen/Autorisieren des Bots.
- **Logging:** Zielkanal und Ereignistypen.
- **Tickets:** Ticket-Kategorien, Support-Rolle, Panel-Kanal, Texte und Schließen/Transkripte.
- **Moderation:** Aktivierte Werkzeuge, Protokollkanal und Anti-Spam-Einstellungen.
- **Rollen & Zugriffe:** Konfiguration nur für Server, für die der angemeldete Nutzer ausreichende Rechte hat.

## Sicherheitsanforderungen
- Der Bot-Token darf niemals an Browser-Code, Frontend-Builds, HTML oder JavaScript ausgeliefert werden.
- Discord OAuth2 Authorization Code Flow mit serverseitig verwaltetem Client-Secret und geprüfter `state`.
- Jede Änderung serverseitig auf die Discord-ID des Servers und die Berechtigung `MANAGE_GUILD` prüfen; eine vom Browser gesendete Guild-ID allein ist kein Berechtigungsnachweis.
- Secrets ausschließlich über Umgebungsvariablen des Hostings.
- Dashboard und Bot verwenden eine gemeinsame persistente Datenbank/Service-Schicht. Keine getrennte lokale SQLite-Datei pro Prozess.
- Einstellungen und Logs werden pro Discord-Server isoliert.
- Bei Datenbank-/Discord-Fehlern klare Fehlermeldungen anzeigen; keine Erfolgsmeldung vor bestätigtem Speichern.

## Umsetzungshinweis
Das Dashboard ist derzeit **noch nicht implementiert**. Diese Datei beschreibt die verbindliche Zielarchitektur. Erst Authentifizierung, Berechtigungsprüfung und persistente Speicherung umsetzen, dann die Konfigurationsseiten. Niemals eine scheinbar funktionierende Oberfläche veröffentlichen, die Einstellungen nicht tatsächlich speichert oder an den Bot übergibt.


## Local run / deployment configuration

Install dependencies from the repository root:

```bash
pip install -r requirements.txt
uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
```

Set these environment variables in the hosting provider's private environment settings (never commit real values):
- `DISCORD_CLIENT_ID`: Discord application's client ID.
- `DISCORD_CLIENT_SECRET`: OAuth2 client secret from Developer Portal → OAuth2.
- `DISCORD_TOKEN`: bot token, server-side only.
- `DASHBOARD_BASE_URL`: public HTTPS URL of the deployed dashboard.
- `SESSION_SECRET`: long random secret used to sign session cookies.
- `ENABLE_MEMBERS_INTENT` and `ENABLE_MESSAGE_CONTENT_INTENT`: set only as required by bot features.

In Discord Developer Portal → OAuth2, register the exact redirect URL:
`https://YOUR-DASHBOARD-DOMAIN/callback`
It must match `DASHBOARD_BASE_URL + /callback` exactly. Use HTTPS in production.

The login route requests `identify guilds`; the invite route requests `bot applications.commands`. Users only see guilds where their OAuth2 permission bitfield contains Manage Server or Administrator.

## Current implementation boundary
The first dashboard implementation provides Discord OAuth login, a server list, an invite redirect, and a first server-settings form backed by the same SQLite module used by the bot. This is an early MVP, not production-ready: the current checkbox settings are persisted but not all are enforced by the bot yet; channel options require the bot to be present and able to fetch guild channels; ticket configuration and role/category pickers still need to be connected. Use only a test server until end-to-end authorization, data persistence and settings enforcement are verified.
