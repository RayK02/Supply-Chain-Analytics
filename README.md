# Lagerhaltungsdaten-App

Web-App zur Analyse der Excel-Arbeitsmappe `Lagerhaltungsdaten` und zusätzlicher aktueller Lagerhaltungsdaten-Exporte.

## Enthalten

- Upload einer Analyse-Arbeitsmappe mit `Artikelposten`
- optionale Blätter `Artikel_Stamm`, `VPE`, `Parameter` und `Lagerhaltungsdaten_IST`
- zusätzlicher Mehrfach-Upload aktueller Lagerhaltungsdatenlisten
- automatische Erkennung des Blatts `Lagerhaltungsdatenübersicht` sowie passender Spalten in anderen Blättern
- anpassbarer Analysezeitraum mit Start- und Enddatum
- frei wählbare Anzahl Durchschnittsmonate von 1 bis 36
- vollständige ABC- und XYZ-Klassifizierung inklusive ABCXYZ
- durchschnittlicher Absatz, Mindestbestandsvorschlag, Wochenbedarf und VPE-gerundete Bestellmenge
- Vergleich mit Lagerbestand, Minimalbestand, Bestellmenge und Maximalbestand aus den aktuellen IST-Dateien
- Anzeige von Lagerort, Beschaffungsmethode und IST-Quelldatei
- Filter, Statusanzeige und XLSX-Export inklusive Quellenübersicht
- keine Anmeldung, keine Datenbank und keine dauerhafte Speicherung der importierten Daten

## Berechnungslogik

- **Startdatum und Enddatum** sind inklusive und bestimmen den Gesamtabsatz sowie die ABC-Klassifizierung.
- **Durchschnittsmonate** bestimmen die letzten N Kalendermonate bis zum Enddatum.
- Der Durchschnittszeitraum wird für Ø Monatsabsatz, XYZ, Mindestbestand und Bestellmenge verwendet.
- Bleiben Start- oder Enddatum leer, verwendet die App den ersten beziehungsweise letzten auswertbaren Verkaufsabgang der Datei.
- Fehlen im Durchschnittsfenster frühere Monate oder beginnt der Analysezeitraum später, werden diese Zeitanteile als Absatz 0 berücksichtigt und als Prüfhinweis angezeigt.
- Der gewählte Zeitraum und alle Berechnungsparameter werden im XLSX-Export im Blatt `Parameter` dokumentiert.

## Speicherung und Datenschutz

- Die drei Eingaben **Durchschnittsmonate**, **Startdatum** und **Enddatum** werden mit `localStorage` ausschliesslich im verwendeten Browser gespeichert.
- Die Einstellungen gelten damit nur auf demselben Gerät und in demselben Browserprofil.
- Hochgeladene Excel-Dateien werden nur während der Anfrage im Arbeitsspeicher verarbeitet.
- Analyseergebnisse werden nicht in einer Datenbank und nicht dauerhaft auf Vercel gespeichert.
- Dauerhaft vorhanden ist nur eine vom Benutzer heruntergeladene XLSX-Auswertung.

## Upload-Ablauf

1. **Analyse-Arbeitsmappe** auswählen. Mindestens erforderlich ist das Blatt `Artikelposten`.
2. Optional eine oder mehrere **aktuelle Lagerhaltungsdatenlisten** auswählen.
3. Durchschnittsmonate sowie optional Start- und Enddatum festlegen.
4. Analyse starten und die Ergebnisse als XLSX exportieren.

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
