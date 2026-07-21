# Datenmodell

- `locations`: eindeutiger Code, Name/Land/Typ, Aktivität, Standardtransport sowie phasen- und gesamtspezifische SLA-Werte.
- `orders`: interne ID und eindeutige Tracking-ID; alternative Referenzen; Standort-FK; zwölf Prozesszeitpunkte; Mengen-, Versand-, Status- und Verantwortungsdaten; Quelle und Audit-Zeitpunkte.
- `events`: append-only Historie mit Typ, Zeitpunkt, Quelle/Akteur, Alt-/Neuwert und Notiz.
- `delay_reasons`: erweiterbare kategorisierte Ursachenliste.
- `import_logs`: Datei/Typ/Zeitpunkt, Zeilenzähler, JSON-Fehler und Warnungen.
- `import_profiles`: Name, Dateityp, Blatt/Kopfzeile und JSON-Spaltenmapping.
- `settings`: versionierbare lokale Key-Value-Konfiguration ohne Geheimnisse.
- `backups`: Inventar der erzeugten SQLite-Sicherungen.

Referenzen sind leer zulässig, werden aber über partielle Unique-Indizes geschützt. `orders.location_id` und `orders.delay_reason_id` sind Fremdschlüssel. Ereignisse werden beim Löschen einer Bestellung kaskadiert; die UI bietet bewusst keine Löschfunktion.

