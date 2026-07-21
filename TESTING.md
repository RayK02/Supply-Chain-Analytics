# Tests

Nach Installation im Projektordner ausführen:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Die Tests verwenden jeweils eine temporäre SQLite-Datenbank. Abgedeckt sind KPI-/Arbeitstagslogik, fehlende und negative Zeitstempel, Statistik/SLA, Status, Duplikate, Alias-Mapping, deutsche Datums- und Dezimalformate, Standort-/Offen-Filter, CSV/XLSX-Export, Hauptseiten sowie Backup und Restore. Ein manueller Produktions-Smoke-Test erfolgt mit `start.bat` und den sieben Beispieldatensätzen.

