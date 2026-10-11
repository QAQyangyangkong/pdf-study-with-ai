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
$env:PYTHONPATH = Join-Path $taskRoot 'backend\src'
& $taskPython -m unittest discover -s backend\tests -t backend -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& $taskPython -m unittest discover -s tests\migration -v
if ($LASTEXITCODE -ne 0) { throw 'Migration tests failed.' }
& $taskPython -m compileall -q backend\src backend\tests tests\migration
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed.' }
pnpm typecheck
if ($LASTEXITCODE -ne 0) { throw 'Frontend type check failed.' }
pnpm test
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
pnpm build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'Backend, migration, frontend tests and production build passed.'
