# Aussenlager Durchlaufzeit Tracker

Lokale deutschsprachige Anwendung zur Messung der vollständigen Durchlaufzeit von Aussenlagerbestellungen – von der Auftragserstellung über Pick, Verpackung und Abholwartezeit bis zum Wareneingang.

## Installation und Start (Windows)

1. `install.bat` doppelklicken. Das Skript erstellt `.venv` und installiert die vier benötigten Pakete.
2. `start.bat` doppelklicken. Der Browser öffnet `http://127.0.0.1:5050`.
3. Zum Beenden `stop.bat` ausführen.

Python 3.11 oder neuer wird benötigt. Die Skripte erkennen auch eine typische Python-Installation, wenn `python` nicht im `PATH` liegt. Es gibt keine Anmeldung, Cloud oder externe Laufzeitabhängigkeit.

## Datenimport

Unter **Import** eine CSV-, TSV- oder XLSX-Datei auswählen. Nach der Vorschau werden Quellspalten auf Zielfelder gemappt. Deutsche und englische Standardnamen werden automatisch erkannt. Für unterschiedliche Exporte kann die Zuordnung als Importprofil gespeichert und beim nächsten Upload ausgewählt werden. Datumswerte wie `21.07.2026`, ISO-Datumswerte und Excel-Datumszellen sowie deutsche/englische Dezimaltrennzeichen werden verarbeitet. `example_import.csv` dient als direkt nutzbare Vorlage.

Duplikate werden über Tracking-ID, Aussenlager-Bestellnummer, AT-Auftrag und externe Belegnummer erkannt. Verfügbare Modi: überspringen, aktualisieren, nur leere Felder ergänzen oder zur manuellen Prüfung überspringen. Vor jedem bestätigten Import wird automatisch ein Backup erstellt.

## KPIs

Die Anwendung berechnet Order-to-Release, Release-to-Pick, Waiting-for-Pick, Pick-Durchlaufzeit, Packzeit, Dokumentenzeit, Order-to-Ready, Ready-to-Pickup, Transport- und Gesamtdurchlaufzeit. Die Anzeige kann zwischen Stunden, Kalendertagen und Arbeitstagen (Mo–Fr) wechseln. Negative Intervalle werden als Datenfehler markiert und nicht in Statistiken verwendet. Median, Mittelwert, Min/Max, P80/P90 sowie SLA-Anteile stehen in der Serviceschicht zur Verfügung; der Median wird im Dashboard hervorgehoben.

## SLA-Konfiguration

Standort-SLA und Standardtransportzeiten liegen in **Stammdaten**. CH, UK und US werden initial angelegt. Globale Warnschwellen und Standardanzeige stehen unter **Einstellungen**. Ein austauschbarer Feiertagskalender ist vorbereitet; Version 1 rechnet Montag bis Freitag.

## Backup und Wiederherstellung

Unter **Systeminformationen** kann ein transaktionales SQLite-Backup erzeugt und heruntergeladen werden. Eine hochgeladene Sicherung wird zuerst per SQLite-Integritätsprüfung validiert. Unmittelbar vor dem Restore wird der aktuelle Zustand automatisch gesichert. Die Datenbank wird nie ungefragt überschrieben.

## Fehlerbehebung

- Port 5050 belegt: `stop.bat` ausführen oder den Port in `start.bat`/`run.py` ändern.
- Python fehlt: Python 3.11+ von python.org installieren und `install.bat` erneut starten.
- XLSX nicht lesbar: Datei in Excel erneut als `.xlsx` speichern; passwortgeschützte Dateien werden nicht unterstützt.
- Importfehler: Importprotokoll und zeilenbezogene Meldungen auf der Importseite prüfen.
- Datenfehler: Die Seite **Datenqualität** öffnet direkt die korrigierbaren Bestellungen.

## Projektstruktur

`app/db.py` enthält Schema und Datenzugriff, `app/services.py` KPIs/Validierung/Status/Backup, `app/imports.py` Dateiimport und Mapping, `app/connectors.py` Adaptergrenzen, `app/routes.py` HTTP-Endpunkte, `app/templates` die UI und `tests` automatisierte Tests. Lokale Laufzeitdaten liegen in `data`, Sicherungen in `backups`.

## Business-Central-Anbindung

Die dateibasierten Connectoren sind produktiv. `BusinessCentralApiConnector` und `NavisionODataConnector` definieren dieselbe normalisierte Schnittstelle, benötigen aber die tatsächlich veröffentlichten Endpunkte und Authentifizierung. Details stehen in [NAVISION_INTEGRATION.md](NAVISION_INTEGRATION.md).

## Optionale Cloud-Version

Die lokale SQLite-Version bleibt der Standard. Mit `DATABASE_URL` kann dieselbe Anwendung Supabase PostgreSQL verwenden und über das enthaltene `render.yaml` kostenlos als Render-Webservice bereitgestellt werden. Die vollständige Anleitung und wichtige Sicherheitshinweise stehen in [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md).
