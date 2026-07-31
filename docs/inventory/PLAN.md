# Umsetzungsplan – Lagerhaltung und ABC/XYZ

## Ziel

Die bestehende Supply-Chain-Analytics-Anwendung erhält ein zusätzliches Lagerhaltungsmodul. Rohdaten werden aus Excel importiert, serverseitig validiert und in Python berechnet. Ergebnisse, Parameter und bestehende Lagerhaltungsdaten werden in SQLite beziehungsweise Supabase PostgreSQL gespeichert und über Vercel bereitgestellt.

## Arbeitspakete

### 1. Datenmodell und Initialisierung

Neue, klar getrennte Tabellen:

- `supplychain_inventory_imports`
- `supplychain_inventory_sales`
- `supplychain_inventory_articles`
- `supplychain_inventory_vpe`
- `supplychain_inventory_ist`
- `supplychain_inventory_parameters`
- `supplychain_inventory_results`
- `supplychain_inventory_changes`

Alle Primärschlüssel sind Text-UUIDs beziehungsweise fachliche Keys. Das Schema wird mit `CREATE TABLE IF NOT EXISTS` initialisiert und funktioniert mit SQLite und PostgreSQL.

### 2. Reine Berechnungslogik

Implementierung als unabhängige Funktionen:

- Artikel-Key normalisieren
- Zahlen und Datumswerte normalisieren
- Verkaufszeilen filtern
- Monatsabsätze aggregieren
- ABC-Klassen berechnen
- XYZ-Klassen berechnen
- Mindestbestand berechnen
- Bestellmenge inklusive VPE-Rundung berechnen
- IST-Abweichung und Status bestimmen

Diese Schicht kennt weder Flask noch SQL und wird vollständig mit pytest getestet.

### 3. Excel-Import

- `.xlsx` validieren
- erwartete Blätter erkennen
- Überschriften über Aliase zuordnen
- `Artikelposten` im Read-only-Modus lesen
- Rohdaten nicht aus berechneten Excel-Zellen übernehmen
- VPE und IST-Daten optional importieren
- Fehler und Warnungen zeilenbezogen sammeln
- Import-ID und Importprotokoll speichern

Standardgrenze: maximal 100'000 Artikelpostenzeilen pro Import. Die Grenze wird konfigurierbar dokumentiert.

### 4. Persistenz und Neuberechnung

Eine Importtransaktion führt aus:

1. Import-Metadaten anlegen
2. Rohdaten validieren
3. Verkaufszeilen speichern
4. Artikelstamm/VPE/IST upserten
5. Parameter laden
6. Analyse berechnen
7. Ergebnisse speichern
8. Importstatus und Zähler aktualisieren

Bei einem Fehler wird die Transaktion zurückgerollt.

Parameteränderungen lösen eine Neuberechnung des letzten erfolgreichen Imports aus.

### 5. Benutzeroberfläche

Eigener Blueprint unter `/inventory`:

- `/inventory` – Dashboard
- `/inventory/import` – XLSX-Upload und Importbericht
- `/inventory/analysis` – ABC/XYZ, Absatz und Vorschläge
- `/inventory/comparison` – IST gegen Vorschlag
- `/inventory/parameters` – fachliche Parameter
- `/inventory/export` – stabiler XLSX-Export

Die Seiten verwenden das bestehende Layout, CSS und die Supabase-Sitzung.

### 6. Vercel

- `api/index.py` exportiert die Flask-App
- `vercel.json` leitet Requests an die Python-Funktion weiter
- temporäre Uploads und Exporte verwenden `/tmp`
- `DATABASE_URL` ist in Preview und Production zwingend
- Supabase PostgreSQL stellt die Persistenz bereit
- Supabase Auth verwendet `SUPABASE_URL` und `SUPABASE_ANON_KEY`
- keine Service-Role im Browser

### 7. Excel-Export

Der Export enthält Werte, keine komplexen Berechnungsformeln:

- README
- Parameter
- ABC_Analyse
- Ø_Absatz_3M
- Lagerhaltungsdaten_IST
- Vergleich_IST_vs_Vorschlag
- Importprotokoll

Qualitätsanforderungen:

- Artikelnummern als Text
- Filter und Freeze Panes
- definierte Zahlen-/Datumsformate
- keine ungültigen Tabellenbereiche
- keine Reparaturmeldung beim Öffnen

### 8. Tests

Pflichttests:

- Key-Normalisierung
- Absatzfilter
- ABC A/B/C
- XYZ X/Y/Z und Nullfall
- Mindestbestand A/B/C
- VPE-Aufrundung
- IST-Status
- Sonderlager
- Kontrollartikel 100602
- Excel-Import
- Excel-Export erneut mit `openpyxl` öffnen
- Flask-Smoke-Tests der neuen Seiten

### 9. Dokumentation

- `docs/inventory/README.md`
- `VERCEL_DEPLOYMENT.md`
- `.env.example` ergänzen
- Abschlussbericht mit Testergebnissen und offenen Punkten

## Datenfluss

`XLSX Upload` → `temporäre Datei` → `Blatt-/Spaltenvalidierung` → `Normalisierung` → `Rohdatenpersistenz` → `ABC/XYZ` → `Bestandsvorschläge` → `IST-Vergleich` → `Dashboard/Export`

## Sicherheits- und Betriebsregeln

- Cloudbetrieb nur mit aktiviertem Supabase-Login
- Uploads werden nach dem Import gelöscht
- Dateinamen werden bereinigt
- maximal erlaubte Dateigrösse bleibt über Flask begrenzt
- SQL-Parameter werden gebunden
- bestehende Tracker-Daten bleiben unverändert
- keine Zugangsdaten im Git-Verlauf

## Rollback

- Feature liegt vollständig auf `feature/inventory-abc-xyz`
- neue Tabellen sind isoliert und beeinflussen bestehende Seiten nicht
- Rollback erfolgt durch Nicht-Mergen beziehungsweise Zurücksetzen des Feature-Commits
- keine destruktiven Datenbankmigrationen erforderlich

## Abnahmekriterien

- bestehende Tests bleiben erfolgreich
- neue Tests sind erfolgreich
- Flask-App startet lokal
- Vercel-Einstieg importiert die App
- Import der Referenzarbeitsmappe funktioniert
- ABC enthält A, B und C bei geeigneter Datenverteilung
- Kontrollartikel 100602 erhält nachvollziehbare Berechnungen
- Sonderlager werden als manuell zu prüfen markiert
- Export lässt sich ohne Reparaturmeldung öffnen
