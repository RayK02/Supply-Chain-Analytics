# Umsetzungsplan – Aussenlager Durchlaufzeit Tracker

## Analyse des Ausgangszustands

Der bereitgestellte Workspace enthält kein bestehendes Repository, Quellcode-Grundgerüst oder Abhängigkeitsmanagement. Auf dem Rechner ist Python 3.12 installiert, jedoch nicht global im `PATH`. Die Anwendung wird deshalb neu aufgebaut; Windows-Skripte erkennen typische Python-Installationen und erklären fehlende Voraussetzungen verständlich.

## Gewählte Architektur

- Lokale Webanwendung mit Python 3.11+, Flask und Waitress
- SQLite als transaktionale, lokal gesicherte Datenbank
- Serverseitig gerenderte Jinja2-Seiten mit eigenem CSS und Vanilla JavaScript
- Diagramme als offlinefähige HTML/SVG/CSS-Visualisierungen, ohne CDN
- `openpyxl` für XLSX-Import und -Export; Standardbibliothek `csv` für CSV
- Schichten: Web-Routen → Services/Geschäftslogik → Repository/SQLite
- Konfiguration über lokale JSON-/Umgebungswerte; Geheimnisse optional über OS-Keyring

Die Architektur vermeidet Node/React und eine separate Datenbank. Sie ist offline, einfach zu starten und lässt Connectoren später hinter einer stabilen Importschnittstelle ergänzen.

## Datenmodell

- `locations`: Standort, Land, Typ, Aktivität und SLA-/Transportvorgaben
- `orders`: Referenzen, Prozesszeitstempel, Mengen-/Versanddaten, Status und Metadaten
- `events`: unveränderliche Prozess- und Änderungshistorie pro Bestellung
- `import_logs`: Datei, Zähler, Fehler und Warnungen eines Imports
- `import_profiles`: wiederverwendbare Spaltenzuordnungen
- `delay_reasons`: konfigurierbare Verzögerungsgründe
- `settings`: globale Warnschwellen und Connector-Konfiguration
- `backups`: erzeugte Sicherungen und Metadaten

Eindeutige, normalisierte Referenzindizes sowie eine Matching-Logik über Tracking-ID, AT-Auftrag, Aussenlager- und externe Belegnummer verhindern Doppelimporte.

## Importstrategie

1. Datei sicher in einen temporären Bereich einlesen (`.csv`, `.xlsx`)
2. Blatt und Kopfzeile erkennen beziehungsweise auswählbar machen
3. Spalten anhand einer deutschen/englischen Alias-Liste vorschlagen
4. Profil speichern, Vorschau und zeilenweise Validierung anzeigen
5. Datums- und Zahlenwerte robust normalisieren
6. Duplikatmodus anwenden: überspringen, aktualisieren oder nur Lücken füllen
7. Vor bestätigtem Grossimport automatische SQLite-Sicherung erstellen
8. Importergebnis vollständig protokollieren

Connectoren implementieren dieselbe Schnittstelle. Datei-Connectoren sind produktiv; BC-API/OData sind sicher konfigurierte, dokumentierte Adaptergerüste ohne fest verdrahtete Tabellenannahmen.

## Berechnungslogik

- Phasen aus den spezifizierten Zeitstempelpaaren
- Einheiten: Stunden, Kalendertage, Arbeitstage (Mo–Fr)
- Median, Mittelwert, Min/Max, P80/P90 und SLA-Quoten
- Offene Laufzeit bis zum aktuellen Zeitpunkt
- Phasenaufteilung: interne Bearbeitung, Abholwartezeit, Transport
- Negative Intervalle werden nicht als KPI verwendet, sondern als Datenqualitätsfehler markiert
- Feiertage werden über eine austauschbare Kalenderfunktion vorbereitet

## Seiten und Funktionen

- Dashboard mit KPI-Karten, Trends, Phasen-, Standort-, SLA- und Altersauswertung
- Bestellübersicht und eigene Ansicht für offene/überfällige Bestellungen
- Bestelldetail mit Timeline, Referenzen, KPIs, Warnungen und Historie
- Manuelle Neuanlage/Bearbeitung mit Validierung und Ereignisprotokoll
- Importassistent mit Vorschau, Mapping, Profilen und Protokollen
- Standortvergleich und Datenqualitäts-Arbeitsliste
- Managementreport, CSV-/XLSX-Exporte
- Stammdaten für Standorte und Verzögerungsgründe
- Einstellungen, Connector-Konfiguration, Backup/Restore und Systeminformationen

## Validierungsregeln

- Tracking-ID, Standort und Bestelldatum als Pflichtfelder
- mindestens eine belastbare Auftragsreferenz
- eindeutige Referenzen und explizite Duplikatbehandlung
- chronologische Plausibilität aller Prozessschritte
- bekannte Statuswerte, nichtnegative Mengen/Werte
- Dateityp-, Dateigrössen- und Tabellenblattprüfung
- fehlende Daten werden sichtbar markiert statt stillschweigend erfunden

## Teststrategie

- Unit-Tests für Arbeitstage, KPI-Intervalle, Statistik und SLA
- Datenbanktests für Duplikate, Status, Filter, Events und offene Aufträge
- Importtests für Alias-Mapping, Datums-/Dezimalformate und Update-Modi
- Backup-/Restore-Test mit Integritätsprüfung
- Flask-Client-Smoke-Tests für alle Hauptseiten, Formulare, Downloads und Buttons
- Endprüfung mit initialisierter Beispieldatenbank und laufendem Waitress/Flask-Server

## Technische Risiken

- NAV-/BC-Exporte variieren stark: Alias- und Profilmapping bleibt deshalb konfigurierbar.
- Feiertage sind in Version 1 nicht vorbefüllt; Arbeitstage sind zunächst Mo–Fr.
- Sehr grosse XLSX-Dateien benötigen Streaming/Grenzen; Dateigrösse und Zeilen werden begrenzt.
- Geheimnisse dürfen nicht in SQLite/Quellcode liegen; ohne verfügbares OS-Keyring werden nur nichtgeheime Connectorwerte gespeichert.
- SQLite eignet sich für den lokalen Einzelplatzbetrieb, nicht für parallelen Mehrbenutzerbetrieb.

## Spätere Navision-/Business-Central-Integration

Eine Connector-Basisklasse liefert normalisierte Datensätze an denselben Importservice. Konfigurierbare Entity-/Feldmappings verbinden je nach System Sales/Purchase Header, Shipment/Receipt sowie Warehouse Activity/Shipment und Change Log. OAuth-Client-Credentials für Business Central und OData für ältere NAV-Systeme werden getrennt behandelt. Benötigt werden vom internen Team: Version, Veröffentlichungen/API-Pages, Firmen-/Mandantenkennung, Schlüsselbeziehungen, Zeitzone, Änderungsprotokollumfang und Authentifizierungsverfahren.
