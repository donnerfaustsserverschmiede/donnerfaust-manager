# Donnerfaust Manager – Changelog

## 2026-10-19 — Changelog-Zustellung korrigiert und Protokollkanäle festgelegt

### Behoben
- Die automatische Veröffentlichung des Changelogs in Discord wurde erfolgreich zugestellt.
- Der GitHub-Actions-Workflow sendet jetzt einen expliziten Discord-konformen `User-Agent`, um die zuvor aufgetretene HTTP-403-/Cloudflare-1010-Blockierung zu vermeiden.
- Die veröffentlichte Nachricht enthält den neuesten Abschnitt aus dieser Datei sowie einen Link zum GitHub-Commit.

### Protokollierung
- Einladungen des DF-Managers auf den zentralen Discord-Server werden für den festgelegten Protokollkanal verarbeitet.
- Verlässt der Bot einen Server oder wird er daraus entfernt, wird dafür ebenfalls ein Protokolleintrag ausgelöst.
- Der Kanal für Einladungen/Entfernungen ist von dem separaten Changelog-Kanal getrennt.
- Eine Entfernungsbenachrichtigung unterscheidet nicht zuverlässig zwischen einem Kick und einem freiwilligen Verlassen des Servers.

### Geprüft
- **Bestätigt:** Die Changelog-Nachricht ist im Discord-Kanal angekommen (manuelle Sichtprüfung am 19.10.2026).
- **Codeänderung gespeichert:** Der Workflow setzt den zusätzlichen `User-Agent`.
- **Noch offen:** Die Live-Zustellung der Einladungs-/Entfernungsprotokolle wurde mit echten Serverereignissen noch nicht separat bestätigt.
- Ein grüner Workflow allein ersetzt keinen vollständigen Ende-zu-Ende-Test aller Bot-Module.

### Nächste Prüfschritte
- Einladungs-/Entfernungsprotokoll mit einem kontrollierten Test verifizieren.
- Dashboard-Anmeldung sowie Ticketsystem, Moderation und Logging jeweils praktisch testen.
- Bei jeder Änderung einen konkreten Eintrag mit Änderung, betroffenen Funktionen und tatsächlichem Teststatus ergänzen.

---

## 2026-10-19 — Projektübersicht und technische Grundlage

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
- Die Funktionen müssen einzeln praktisch getestet werden, bevor sie als vollständig bestätigt gelten.

### Qualitätssicherung
- Ein automatisierter Prüfworkflow für grundlegende Python-Syntax- und Importprüfungen ist vorhanden.
- Ein erfolgreicher CI-Lauf bestätigt nur die konkret ausgeführten automatisierten Prüfungen und nicht die fehlerfreie Live-Funktion aller Discord-Funktionen.

---

