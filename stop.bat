@echo off
powershell -NoProfile -Command "$p=Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if($p){Stop-Process -Id $p; Write-Host 'Tracker beendet.'}else{Write-Host 'Kein laufender Tracker gefunden.'}"

