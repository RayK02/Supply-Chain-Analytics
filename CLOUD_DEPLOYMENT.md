# Kostenlose Cloud-Bereitstellung

Die lokale App bleibt unverändert mit SQLite nutzbar. Sobald `DATABASE_URL` gesetzt ist, verwendet dieselbe Anwendung PostgreSQL – vorgesehen ist der kostenlose Supabase-Pooler.

## 1. Supabase-Projekt

1. In Supabase ein Free-Projekt namens `supply-chain-analytics` anlegen.
2. Region Frankfurt beziehungsweise die nächstgelegene EU-Region wählen.
3. Unter **Connect → Transaction pooler** die PostgreSQL-Verbindungszeichenfolge kopieren.
4. Das Datenbankpasswort nur im Render-Secret `DATABASE_URL` einsetzen. Niemals in GitHub committen.

Beim ersten Start legt die Anwendung Tabellen, Indizes, Standorte, SLA-Werte und Beispieldaten automatisch an.

## 2. Render-Webservice

1. Bei Render kostenlos mit GitHub anmelden.
2. **New → Blueprint** wählen und `RayK02/Supply-Chain-Analytics` verbinden.
3. Render erkennt `render.yaml` und erstellt den kostenlosen Webservice `supply-chain-analytics`.
4. Bei der abgefragten Umgebungsvariable `DATABASE_URL` die Supabase-Pooler-URL als Secret eintragen.
5. Deployment starten und anschließend `/health` prüfen.

## Kostenlose Limits

- Render Free schläft nach 15 Minuten ohne Zugriff ein; der erste neue Aufruf kann etwa eine Minute dauern.
- Das lokale Dateisystem von Render ist flüchtig. Dauerhafte Bestelldaten liegen deshalb in Supabase PostgreSQL.
- Supabase Free umfasst bis zu zwei Projekte und 500 MB Datenbank; ein Projekt kann nach einer Woche Inaktivität pausiert werden.
- Für geschäftskritischen Dauerbetrieb sind später kostenpflichtige Pläne, Monitoring und ein formelles Backup-Konzept notwendig.

## Sicherheit

- `DATABASE_URL`, Datenbankpasswort und sonstige Secrets ausschließlich als Render Environment Secrets speichern.
- Die App besitzt weiterhin keine Anmeldung. Die kostenlose Online-Version ist daher nur für Testdaten geeignet und darf nicht mit vertraulichen Unternehmensdaten öffentlich betrieben werden.
- Vor einem produktiven Internetbetrieb müssen Authentifizierung, Rollen, TLS-/Header-Härtung, Datenschutzprüfung und ein Backup-/Restore-Prozess ergänzt werden.
