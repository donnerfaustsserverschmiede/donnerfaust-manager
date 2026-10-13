# Donnerfaust Manager

Ein modularer Discord-Verwaltungsbot mit **Web-Dashboard als zentraler Bedienoberfläche**. Inspiriert von Bot-Dashboards wie Carl-bot und Galaxy Bot: Server auswählen, Bot einladen und Einstellungen über die Website verwalten.

## Ziel: Eine Website für alle Einstellungen
- Discord-Anmeldung
- Serverübersicht mit Berechtigungsprüfung
- **Bot einladen**-Schaltfläche
- Logging: Zielkanal und Ereignisse konfigurieren
- Tickets: Kategorien, Support-Rolle, Panel-Kanal und Texte konfigurieren
- Moderation: Funktionen und Protokollierung konfigurieren
- Einstellungen getrennt je Discord-Server

Die Website soll keine Einstellungen nur optisch anzeigen: Jede Änderung muss sicher gespeichert und vom Bot verwendet werden. Der Bot-Token bleibt ausschließlich im serverseitigen Hosting und wird niemals an den Browser oder GitHub ausgeliefert.

## Schubladen / Module
- `app/modules/logging_module/` — Logging
- `app/modules/tickets/` — Tickets
- `app/modules/moderation/` — Moderation
- `app/core/` — gemeinsame technische Grundlage
- `dashboard/` — Web-Dashboard (Spezifikation vorhanden; Umsetzung steht noch aus)

## Aktueller Stand
- Discord-Bot-Grundgerüst und Modul-Ladesystem vorhanden.
- Erste Logging-Funktionen implementiert.
- Einfache Ticket- und Moderationsfunktionen ergänzt, noch nicht live getestet.
- Bot-Einladungslink ist über Discord OAuth2 generierbar; die Dashboard-Schaltfläche ist noch nicht gebaut.
- **Web-Dashboard, Discord-Login, Berechtigungsprüfung und gemeinsame persistente Datenbank sind noch nicht implementiert.**
- Hosting und End-to-End-Tests stehen aus.

## Sicherheits- und Hostinghinweise
- Echte Tokens/Secrets niemals in GitHub committen oder im Chat teilen.
- Discord Developer Portal Intents nur einschalten, wenn eine Funktion sie benötigt.
- Ein gehosteter Bot braucht einen laufenden Prozess und dauerhafte Speicherung. Kostenlose Hosting-Angebote können schlafen gehen, begrenzt sein oder ihre Konditionen ändern.

Weitere Details: `docs/ARCHITECTURE.md` und `dashboard/README.md`.
