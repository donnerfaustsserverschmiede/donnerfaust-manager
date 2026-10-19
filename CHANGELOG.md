# Donnerfaust Manager – Changelog

## 2026-10-19 — Erstes Gesamt-Update: Projektstand und Changelog-Automatik

Der Donnerfaust Manager wird als modularer Discord-Bot mit zentralem Web-Dashboard entwickelt. Ziel ist es, wichtige Verwaltungsfunktionen an einem Ort zusammenzuführen und die Bedienung über eine Webseite zu vereinfachen.

### Bot und technische Grundlage
- Der Bot wird in Python entwickelt.
- Die Funktionen sind in separate Module aufgeteilt, damit sie unabhängig erweitert und gewartet werden können.
- Die Erweiterungsverwaltung lädt die Bot-Module beim Start.
- GitHub wird für Quellcode und Versionsverwaltung verwendet.
- Render ist als Hosting-Plattform für den Bot beziehungsweise das Dashboard vorgesehen.

### Dashboard und Anmeldung
- Eine Web-Verwaltungsoberfläche auf Basis von FastAPI ist Teil des Projekts.
- Discord-OAuth2 ist für die Anmeldung an der Verwaltungsoberfläche vorgesehen.
- Die Oberfläche ist auf getrennte Verwaltungsbereiche für Ticketsystem, Moderation und Logging ausgelegt.
- Ziel ist, Einstellungen zentral über das Dashboard zu verwalten.

### Ticketsystem, Moderation und Logging
- Ticketsystem, Moderation und Logging sind als eigenständige Funktionsbereiche vorgesehen.
- Das Ticketsystem soll über das Dashboard konfigurierbar sein.
- Der Bot soll Einladungen auf einen Discord-Server und das Entfernen von einem Server im festgelegten zentralen Protokollkanal melden.
- Eine Entfernungsmeldung dokumentiert, dass der Bot den Server verlassen hat beziehungsweise entfernt wurde; sie kann nicht in jedem Fall beweisen, ob ein Administrator ihn gekickt hat.

### Automatischer Changelog
- Ein GitHub-Actions-Workflow veröffentlicht Changelog-Einträge automatisch im Discord-Changelog-Kanal.
- Ausführliche Einträge werden in dieser Datei `CHANGELOG.md` gepflegt.
- Der Workflow nimmt den neuesten Abschnitt dieser Datei und ergänzt einen Verweis auf den GitHub-Commit.
- Änderungen am Hauptbranch lösen die Veröffentlichung aus; ein manueller Workflow-Start ist ebenfalls vorgesehen.
- Der Webhook wird als geschütztes GitHub-Repository-Secret `DISCORD_CHANGELOG_WEBHOOK` gespeichert und nicht im Quellcode abgelegt.

### Qualitätssicherung und aktueller Status
- Ein automatisierter Prüfworkflow für grundlegende Python-Syntax- und Importprüfungen ist vorhanden.
- Ein erfolgreicher CI-Lauf bestätigt die durchgeführten automatisierten Prüfungen, aber keinen vollständigen Ende-zu-Ende-Test aller Discord-Funktionen.
- Die tatsächliche Zustellung der Changelog-Nachricht sowie die Live-Funktion von Dashboard, Tickets, Moderation und Server-Ereignisprotokollen müssen anhand ihrer jeweiligen Workflow-Läufe beziehungsweise praktischer Discord-Tests bestätigt werden.

### Vorgehen bei künftigen Änderungen
Bei jeder weiteren Bot-Änderung soll der passende Abschnitt in dieser Datei ergänzt werden: Was wurde geändert, welche Funktion betrifft es, welche Fehler wurden behoben und was wurde tatsächlich getestet. Der neueste Abschnitt wird anschließend automatisch im Discord-Changelog veröffentlicht.

---
