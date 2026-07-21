$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir
$PythonCandidates = @(
  (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
  "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
if (-not $PythonCandidates) { throw 'Python 3.11 oder neuer wurde nicht gefunden. Bitte von python.org installieren und Setup erneut starten.' }
$PythonExe = $PythonCandidates[0]
& $PythonExe -m venv "$ProjectDir\.venv"
& "$ProjectDir\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$ProjectDir\.venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"
& "$ProjectDir\.venv\Scripts\python.exe" -c "from app import create_app; create_app()" 2>$null
Write-Host 'Setup abgeschlossen. Starten Sie nun start.bat.' -ForegroundColor Green
