# Donnerfaust Manager

Der **Donnerfaust Manager** ist eine zentrale Weboberfläche für den Discord-Bot. Die Website soll alle Funktionen über ein gemeinsames Dashboard mit Menü, Discord-Anmeldung und serverbezogenen Einstellungen zugänglich machen.

## So ist das Projekt aufgeteilt

- **GitHub** enthält den Quellcode und die Versionshistorie.
- **Render** betreibt die Python-Webanwendung und den Discord-Bot.
- **Eine gemeinsame Website** enthält Startseite, Discord-Login, Serverauswahl, Logging, Ticketsystem, Moderation und Kontoverwaltung. Die Funktionen werden schrittweise vollständig angebunden.

GitHub Pages kann die Python-Anwendung nicht ausführen. Die eigentliche interaktive Verwaltungsoberfläche muss deshalb über den Render-Webdienst geöffnet werden. Es ist keine zweite, getrennte Verwaltungswebsite vorgesehen.

## Funktionen und aktueller Stand

- Discord-OAuth-Anmeldung mit serverseitig geprüftem OAuth-Status.
- Serverübersicht mit Berechtigungsprüfung für „Server verwalten“ oder Administrator.
- Bot-Einladung über Discord.
- Logging: Auswahl eines Log-Kanals und Aktivierung unterstützter Ereignistypen; Einstellungen werden serverbezogen gespeichert.
- Ticketsystem und Moderation: derzeit noch nicht vollständig an die Bot-Funktionen angebunden.
- Konto- und Plattformverwaltung mit geschützten Admin-Aktionen.

## Projektstruktur

- `bot.py` — Discord-Bot
- `app/core/` — gemeinsame technische Grundlage und Einstellungen
- `app/modules/logging_module/` — Logging
- `app/modules/tickets/` — Tickets
- `app/modules/moderation/` — Moderation
- `dashboard/app.py` — Web-Dashboard und Routen
- `docs/` — Architektur und Projektdokumentation

## Hosting und Sicherheit

Die Anwendung wird als Webdienst mit dem Startbefehl aus dem `Procfile` betrieben. Benötigte Zugangsdaten werden ausschließlich als private Umgebungsvariablen in Render hinterlegt.

Wichtige Variablen:
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_TOKEN`
- `DASHBOARD_BASE_URL`
- `SESSION_SECRET`

Das Bot-Token gehört niemals in HTML, JavaScript, GitHub-Dateien oder den Browser. Die OAuth2-Callback-URL in Discord muss exakt `DASHBOARD_BASE_URL + /callback` entsprechen.

**Hinweis:** Einstellungen sollten erst auf einem Testserver als produktionsbereit betrachtet werden, wenn die jeweilige Funktion vollständig vom Bot übernommen und Ende-zu-Ende geprüft wird.

## Wirtschaft & Handel (neu)
Das Modul `app/modules/trade/` wird vom bestehenden Bot geladen und ergänzt ihn um:
- `/artikel_anlegen`: Artikel, Kategorie sowie Ein- und Verkaufspreis anlegen.
- `/lagerbestand`: kompletten Artikelbestand anzeigen, nach Name/Kategorie filtern und seitenweise blättern.
- `/einlagern` und `/auslagern`: Lagerbewegungen mit Mitarbeiter und Notiz protokollieren; negative Bestände werden verhindert.
- `/preis_setzen`: Verkaufspreis und optional Einkaufspreis ändern.
- `/verkauf` und `/einkauf`: Handel mit Menge, Handelspartner und Stückpreis buchen; Lager und Kassenbuch werden in einer Datenbanktransaktion aktualisiert.
- `/preisliste`: eigene Verkaufspreise anzeigen.
- `/buchungen`: letzte Lager- und Handelsvorgänge anzeigen.
- `/kassenbuch`: letzte Finanzbuchungen anzeigen.
- `/bilanz`: Einnahmen, Ausgaben, Netto-Cashflow und rechnerischen Lagerwert anzeigen.

Die Handelsdaten werden nach Discord-Server getrennt in derselben SQLite-Datenbank wie die bestehenden Einstellungen gespeichert. Für produktiven Betrieb auf Render muss sichergestellt sein, dass der Datenbankpfad auf einem persistenten Datenträger liegt oder die Datenbank auf einen dauerhaften PostgreSQL-Dienst migriert wird. Ein flüchtiges Dateisystem ist keine sichere dauerhafte Speicherung.
