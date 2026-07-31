# Analyse – Lagerhaltung, ABC/XYZ und Vercel

## Auftrag

Das bestehende Repository wird um eine webbasierte Lagerhaltungsanalyse erweitert. Die neue Funktion übernimmt die fachliche Logik der Arbeitsmappe `Lagerhaltungsdaten_Q1.26_ABC_NEU_mit_ABCXYZ_FIX.xlsx`, berechnet die Ergebnisse jedoch serverseitig und exportiert überwiegend Werte statt fragiler Excel-Formeln.

## Bestehender Repository-Zustand

- Framework: Python/Flask mit serverseitigen Jinja-Templates und eigenem CSS.
- Persistenz: lokal SQLite; optional PostgreSQL/Supabase über `DATABASE_URL`.
- Datenzugriff: gemeinsame Kompatibilitätsschicht für SQLite und PostgreSQL in `app/db.py`.
- Dateiimport: CSV/XLSX mit `openpyxl`, Vorschau und Mapping für den bestehenden Durchlaufzeit-Tracker.
- Tests: pytest mit Flask-Testclient und Datenbanktests.
- Cloud: Render-Konfiguration ist vorhanden.
- Authentifizierung: Der offene Branch/PR `agent/supabase-login` ergänzt Supabase-E-Mail/Passwort-Login. Der Feature-Branch basiert auf diesem Stand, damit die Lagerdaten nicht öffentlich erreichbar sind.
- Das bestehende Projekt ist kein Next.js-Projekt. Ein vollständiger Framework-Wechsel würde den funktionierenden Tracker, die Tests und die Datenzugriffsschicht unnötig duplizieren. Deshalb wird Flask beibehalten und für Vercel als Python-Serverless-Anwendung konfiguriert.

## Analysierte Excel-Arbeitsmappe

Erkannte Tabellenblätter:

1. `Artikelposten` – 49'606 Datenzeilen, 23 Spalten
2. `Artikel_Stamm` – 509 Artikelzeilen
3. `ABC_Analyse` – 509 Artikelzeilen, ABC- und XYZ-Berechnungen
4. `Ø_Absatz_3M` – Absatz, Mindestbestand und Bestellmenge
5. `Lagerhaltungsdaten_IST` – bestehende Navision-Lagerhaltungsparameter
6. `VPE` – Verpackungseinheiten und Palettenmengen
7. `Parameter` – fachliche Grenzwerte und Faktoren

### Relevante Quelldaten

`Artikelposten`:

- Buchungsdatum
- Belegart
- Artikelnr.
- Beschreibung
- Lagerortcode
- Menge
- Variantencode

`Lagerhaltungsdaten_IST`:

- Artikelnr.
- Variantencode
- Lagerortcode
- Beschaffungsmethode
- Beschreibung
- Lagerbestand
- Minimalbestand
- Bestellmenge
- Maximalbestand

`VPE`:

- Art. Nummer
- Beschreibung
- VPE
- Erweiterte Mengen Palette

## Fachliche Logik der Arbeitsmappe

### Artikel-Key

Artikelnummern werden auf einen sechsstelligen Text-Key normalisiert.

- `40` → `000040`
- `000040` → `000040`
- `100602` → `100602`
- `100602.0` → `100602`

Die Excel-Datei nutzt dafür Hilfsspalten. In der App erfolgt die Normalisierung zentral und wird getestet.

### Absatz

- Standard-Belegart: `Verkaufslieferung`
- Nur Mengen kleiner null zählen als Verkaufsabgang.
- Die negative Menge wird als positiver Absatz dargestellt.
- Stichtag: höchstes gültiges Buchungsdatum.
- Standardzeitraum: drei Monate.
- Ø Monatsabsatz: Absatz im Zeitraum / Anzahl Monate.
- Wochenbedarf: Ø Monatsabsatz × 12 / 52.

### ABC

- A-Grenze kumuliert: 80 %
- B-Grenze kumuliert: 95 %
- Rest: C

Die App muss intern nach Absatz absteigend sortieren. Die Klassierung darf nicht von der sichtbaren Sortierung einer Tabelle abhängen.

### XYZ

Basis sind die Monatsabsätze der letzten drei Stichtagsmonate:

- M-2
- M-1
- M0

Berechnung:

- Mittelwert der drei Monatswerte
- Populationsstandardabweichung
- Variationskoeffizient = Standardabweichung / Mittelwert

Grenzen:

- X: VK ≤ 0,50
- Y: VK ≤ 1,00
- Z: VK > 1,00

Monate ohne Absatz zählen mit null. Bei Mittelwert null wird keine XYZ-Klasse erfunden; stattdessen wird eine Begründung gespeichert.

### Mindestbestand

- A: 3 Monatsabsätze
- B: 2 Monatsabsätze
- C: 2 Monatsabsätze

Formel:

`Ø Monatsabsatz × ABC-Faktor`, auf ganze Stück aufgerundet.

Die VPE ist standardmässig nur eine Information und verändert den Mindestbestand nicht.

### Bestellmenge

Bestellintervalle:

- A: 2 Wochen
- B: 4 Wochen
- C: 8 Wochen

Formel:

`Wochenbedarf × Bestellintervall`, danach bei vorhandener positiver VPE auf das nächste VPE-Vielfache aufrunden.

### IST-Vergleich

Automatisch bewertet wird standardmässig nur Lagerort `FERTIG`. Sonderlager wie `AUSTAUSCH`, `DEFEKT` und `ERSATZ` erhalten `Manuell prüfen`.

Bewertungen:

- OK
- Erhöhen
- Reduzieren
- Kein Vorschlag
- Manuell prüfen

## Kontrollartikel 100602

Die Arbeitsmappe enthält für Artikel `100602` die fachliche Kontrolllogik:

- ABC-Klasse A
- Mindestbestand = Ø Monatsabsatz × Faktor A
- Faktor A = 3
- Bestellintervall A = 2 Wochen
- vorhandene VPE wird für die Bestellmengenrundung verwendet

Die gespeicherten Excel-Formelergebnisse sind in der Datei teilweise leer, weil `openpyxl` Formeln nicht berechnet und die Arbeitsmappe nicht überall einen aktuellen Excel-Cache enthält. Die App darf deshalb keine berechneten Excel-Zellen als Quelle verwenden, sondern muss aus den Rohdaten neu rechnen.

## Gefundene Risiken

1. **Formel- und Cache-Abhängigkeit:** Berechnete Zellen können leer oder veraltet sein.
2. **Artikelnummer Zahl/Text:** Führende Nullen und `.0` führen sonst zu nicht gefundenen Artikeln.
3. **ABC-Grenzfall:** Eine rein zeilenbasierte, unsortierte Excel-Formel kann falsche Klassen erzeugen.
4. **XYZ bei Nullabsatz:** Division durch null muss fachlich begründet abgefangen werden.
5. **VPE null/negativ:** Darf keine Rundung auslösen.
6. **Sonderlager:** Dürfen nicht automatisch anhand normaler Verkaufsdaten angepasst werden.
7. **Vercel-Dateisystem:** Nur `/tmp` ist zur Laufzeit beschreibbar; persistente Daten müssen in Supabase PostgreSQL liegen.
8. **Serverless-Laufzeit:** Sehr grosse Excel-Dateien müssen speicherschonend gelesen und begrenzt werden.
9. **Bestehende Tabellen:** Neue Tabellen erhalten den Präfix `supplychain_inventory_`; bestehende Tracker-Tabellen werden nicht gelöscht oder umbenannt.
10. **Authentifizierung:** Die Lagerdaten dürfen in der Cloud nicht ohne Login betrieben werden. Der Feature-Branch enthält daher den Stand des Supabase-Login-Branches.

## Architekturentscheidung

Die bestehende Flask-Anwendung wird modular erweitert:

- `app/inventory_schema.py`: nicht-destruktives Schema und Standardparameter
- `app/inventory_calculations.py`: reine, getestete Fachlogik
- `app/inventory_import.py`: XLSX-Parsing und Validierung
- `app/inventory_service.py`: Persistenz, Importtransaktion, Vergleiche, Export
- `app/inventory_routes.py`: eigener Blueprint `/inventory`
- `app/templates/inventory/*`: UI
- `api/index.py` und `vercel.json`: Vercel-Einstieg

Diese Lösung erhält den bestehenden Aussenlager-Tracker und dessen Datenmodell. Supabase wird über die bereits vorhandene PostgreSQL-Verbindung genutzt; es werden keine fremden Supabase-Projekte oder Tabellen automatisiert verändert.

## Nicht-destruktive Regeln

- kein `DROP TABLE`
- kein `TRUNCATE`
- kein `CASCADE`
- keine Änderung bestehender Tabellen
- keine Secrets im Repository
- Rohdatenimporte bleiben über eine Import-ID nachvollziehbar
- Änderungen an IST-Werten werden historisiert
