# Lagerhaltungsdaten-App

Web-App zur Analyse der Excel-Arbeitsmappe `Lagerhaltungsdaten`.

## Enthalten

- Upload einer XLSX-Arbeitsmappe
- automatische Erkennung der Blätter `Artikelposten`, `Artikel_Stamm`, `Lagerhaltungsdaten_IST`, `VPE` und optional `Parameter`
- vollständige ABC- und XYZ-Klassifizierung inklusive ABCXYZ
- durchschnittlicher Absatz, Mindestbestandsvorschlag, Wochenbedarf und VPE-gerundete Bestellmenge
- Vergleich mit den aktuellen Lagerhaltungsdaten
- Filter, Statusanzeige und XLSX-Export
- keine Anmeldung, keine Datenbank, kein Aussenlager-Tracker und keine dauerhafte Speicherung der importierten Daten

## Lokal starten

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python webapp.py
```

Danach `http://127.0.0.1:5050` öffnen.

## Vercel

Das Repository ist direkt für Vercel vorbereitet. Das bestehende Vercel-Projekt kann weiterhin mit `main` verbunden bleiben.

## Erwartete Quelldaten

Die App verwendet deutsche und englische Spaltenaliase. Mindestens erforderlich sind im Blatt `Artikelposten`:

- Artikelnummer
- Buchungsdatum
- Belegart
- Menge

Als Verkaufsabgang gelten negative Mengen der in `Parameter` definierten Belegart, standardmässig `Verkaufslieferung`.
