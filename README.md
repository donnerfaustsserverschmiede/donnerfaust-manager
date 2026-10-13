# Donnerfaust Manager

Kostenlos geplanter, modularer Discord-Verwaltungsbot mit eigener Web-Verwaltung.

## Das Schubladensystem
Jede Funktion ist ein eigenes Modul. Änderungen an einer Schublade sollen die anderen möglichst nicht beeinflussen.

- **Logging** — `app/modules/logging_module/`
- **Ticketsystem** — `app/modules/tickets/`
- **Moderation** — `app/modules/moderation/`
- **Web-Dashboard** — `dashboard/` (separate Anwendung, geplant)
- **Gemeinsame Bot-Grundlage** — `app/core/`
- **Bot-Start** — `bot.py`

## Logging-Modul (erste Ausbaustufe)
1. Erstelle in deinem Discord-Server einen privaten Textkanal für Logs.
2. Gib dem Bot in diesem Kanal die Rechte **Kanal ansehen**, **Nachrichten senden** und **Links einbetten**.
3. Als Server-Administrator: `!setlogchannel #dein-logkanal`
4. Prüfen: `!logstatus`

Aktuell protokolliert das Modul Nachrichtenbearbeitungen/-löschungen, Mitgliederbeitritte/-austritte, erstellte/gelöschte Kanäle und Rollen sowie Sprachkanalwechsel. Discord kann je nach Ereignis und Berechtigungen Details nicht liefern.

## Discord-Intents
Damit Mitgliederereignisse und Nachrichtentexte protokolliert werden können:
- Im Discord Developer Portal unter **Bot** die **Server Members Intent** und **Message Content Intent** aktivieren.
- In der lokalen `.env` die entsprechenden Optionen auf `true` setzen:
  `ENABLE_MEMBERS_INTENT=true`
  `ENABLE_MESSAGE_CONTENT_INTENT=true`

Aktiviere nur die Intents, die deine Bot-Funktionen benötigen. Teile deinen Bot-Token niemals mit anderen und committe ihn nicht in GitHub.

## Architekturregeln
1. Feature-Code bleibt im jeweiligen Modul.
2. Module werden zentral in `app/core/extensions.py` registriert und geladen.
3. Ein Modul soll beim Laden eines anderen Moduls nicht dessen interne Dateien bearbeiten müssen.
4. Einstellungen werden pro Discord-Server gespeichert, nicht fest im Code hinterlegt.
5. Zugangsdaten gehören in eine lokale `.env`-Datei. Echte Tokens niemals committen.
6. Gemeinsame Funktionen kommen nur in `app/core/`, wenn sie wirklich von mehreren Modulen benötigt werden.
7. Vor größeren Änderungen testen wir das betroffene Modul und anschließend den Start des gesamten Bots.

## Start lokal
1. Python 3.11 oder neuer installieren.
2. Abhängigkeiten installieren: `pip install -r requirements.txt`
3. `.env.example` als `.env` kopieren und den Discord-Bot-Token lokal eintragen.
4. Bot starten: `python bot.py`

Die Datenbank wird beim ersten Zugriff lokal unter `data/donnerfaust_manager.sqlite3` angelegt. Die aktuelle SQLite-Lösung ist ein einfacher Startpunkt; für ein dauerhaft gehostetes Multi-Server-Dashboard prüfen wir später gemeinsam eine passende persistente Datenbank.

## Entwicklungsstand
Die modulare Grundstruktur steht. Das Logging-Modul ist die erste funktionale Ausbaustufe; Ticketsystem, Moderation und Dashboard sind aktuell noch Gerüste und werden separat implementiert und getestet.

Weitere Architekturhinweise: `docs/ARCHITECTURE.md`.
