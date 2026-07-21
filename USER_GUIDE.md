# Benutzerhandbuch

## Täglicher Ablauf

Auf dem Dashboard Zeitraum, Standort und Einheit wählen. Kritische offene Bestellungen führen per Klick zur Timeline. Unter **Bestellungen** stehen Suche, Filter, clientseitige Sortierung, Spaltenauswahl und Export bereit. Grau/„unbekannt“ bedeutet fehlender Zeitstempel, Grün/✓ innerhalb SLA, Orange/△ gefährdet und Rot/! überschritten.

## Erfassung und Korrektur

**Bestellung** öffnet das Formular. Tracking-ID, Standort, Bestelldatum und mindestens eine Auftragsreferenz sind Pflicht. Unlogische Zeitfolgen und Duplikate blockieren das Speichern. Jede Änderung erzeugt einen Eintrag in der Ereignishistorie.

## Import

Datei auswählen, gegebenenfalls Tabellenblatt/Kopfzeile setzen, vorgeschlagene Zuordnung prüfen, Vorschau kontrollieren, Duplikatmodus wählen und bestätigen. Ein Profilname bewahrt die Zuordnung für nachvollziehbare Folgeimporte. Fehlerhafte Zeilen werden einzeln genannt und übersprungen; erfolgreiche Zeilen bleiben erhalten.

## Analyse

**Standortvergleich** trennt Bereitstellung und Transport und gibt eine erste ursachenorientierte Einordnung. **Datenqualität** listet fehlende Referenzen, unlogische Reihenfolgen, Ausreisser und unbekannte Status. **Reports** erzeugt eine druckbare Management-Zusammenfassung, die sich auch als PDF drucken lässt.

## Administration

Standorte, SLA und Verzögerungsgründe unter **Stammdaten** pflegen. Warnschwellen und BC/NAV-Konfigurationsmetadaten unter **Einstellungen** hinterlegen. Keine Secrets dort eingeben. Backups unter **Systeminformationen** erzeugen, herunterladen oder nach Integritätsprüfung wiederherstellen.

