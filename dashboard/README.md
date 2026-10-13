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
