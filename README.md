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

## Architekturregeln

1. Feature-Code bleibt im jeweiligen Modul.
2. Module werden zentral in `app/core/extensions.py` registriert und geladen.
3. Ein Modul soll beim Laden eines anderen Moduls nicht dessen interne Dateien bearbeiten müssen.
4. Einstellungen werden pro Discord-Server gespeichert, nicht fest im Code hinterlegt.
5. Zugangsdaten gehören in eine lokale `.env`-Datei. Echte Tokens niemals committen.
6. Gemeinsame Funktionen kommen nur in `app/core/`, wenn sie wirklich von mehreren Modulen benötigt werden.
7. Vor größeren Änderungen testen wir das betroffene Modul und anschließend den Start des gesamten Bots.

## Entwicklungsstand

Die modulare Grundstruktur und leere Modul-Gerüste sind angelegt. Logging, Ticketsystem, Moderation, Datenbank und Dashboard werden anschließend einzeln implementiert und getestet.

## Start lokal

1. Python 3.11 oder neuer installieren.
2. Abhängigkeiten installieren: `pip install -r requirements.txt`
3. `.env.example` als `.env` kopieren und den Discord-Bot-Token lokal eintragen.
4. Bot starten: `python bot.py`

Privilegierte Discord-Intents erst aktivieren, wenn sie im Developer Portal freigeschaltet und für eine konkrete Funktion erforderlich sind.

Weitere Architekturhinweise: `docs/ARCHITECTURE.md`.
