$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install requirements first.' }
$taskTemp = Join-Path $taskRoot 'tmp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $taskRoot 'src'
& $taskPython -m unittest discover -s tests -t . -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $taskPython -m compileall -q src tests launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed.' }
& $taskPython -m study_desk --smoke-test --data-dir (Join-Path $taskTemp 'source-smoke') --report (Join-Path $taskTemp 'source-smoke.json')
if ($LASTEXITCODE -ne 0) { throw 'Source UI smoke test failed.' }
Write-Host 'All tests, compilation and source UI checks passed.'
