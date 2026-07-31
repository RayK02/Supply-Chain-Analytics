# Lagerhaltungsdaten-App

Web-App zur Analyse der Excel-Arbeitsmappe `Lagerhaltungsdaten` und zusätzlicher aktueller Lagerhaltungsdaten-Exporte.

## Enthalten

- Upload einer Analyse-Arbeitsmappe mit `Artikelposten`
- optionale Blätter `Artikel_Stamm`, `VPE`, `Parameter` und `Lagerhaltungsdaten_IST`
- zusätzlicher Mehrfach-Upload aktueller Lagerhaltungsdatenlisten
- automatische Erkennung des Blatts `Lagerhaltungsdatenübersicht` sowie passender Spalten in anderen Blättern
- vollständige ABC- und XYZ-Klassifizierung inklusive ABCXYZ
- durchschnittlicher Absatz, Mindestbestandsvorschlag, Wochenbedarf und VPE-gerundete Bestellmenge
- Vergleich mit Lagerbestand, Minimalbestand, Bestellmenge und Maximalbestand aus den aktuellen IST-Dateien
- Anzeige von Lagerort, Beschaffungsmethode und IST-Quelldatei
- Filter, Statusanzeige und XLSX-Export inklusive Quellenübersicht
- keine Anmeldung, keine Datenbank und keine dauerhafte Speicherung der importierten Daten

## Upload-Ablauf

1. **Analyse-Arbeitsmappe** auswählen. Mindestens erforderlich ist das Blatt `Artikelposten`.
2. Optional eine oder mehrere **aktuelle Lagerhaltungsdatenlisten** auswählen.
3. Analyse starten und die Ergebnisse als XLSX exportieren.

Zusätzliche IST-Dateien überschreiben gleichrangige eingebettete Werte aus `Lagerhaltungsdaten_IST`. Bei mehreren Lagerorten wird gemäss den Parametern zuerst ein automatischer Lagerort wie `FERTIG`, danach ein manueller Sonderlagerort und zuletzt ein anderer Lagerort verwendet.

## Unterstützte IST-Spalten

- `Artikelnr.` / Artikelnummer
- `Variantencode`
- `Lagerortcode`
- `Beschaffungsmethode`
- `Beschreibung`
- `Lagerbestand`
- `Minimalbestand` oder `Mindestbestand`
- `Bestellmenge`
- `Maximalbestand`

## Lokal starten

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python webapp.py
```

Danach `http://127.0.0.1:5050` öffnen.

## Vercel

Das Repository ist direkt für Vercel vorbereitet. `server.py` stellt den Flask-WSGI-Entrypoint bereit; das bestehende Vercel-Projekt kann mit `main` verbunden bleiben.

## Erwartete Absatzdaten

Mindestens erforderlich sind im Blatt `Artikelposten`:

- Artikelnummer
- Buchungsdatum
- Belegart
- Menge

Als Verkaufsabgang gelten negative Mengen der in `Parameter` definierten Belegart, standardmässig `Verkaufslieferung`.
