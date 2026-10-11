$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $taskRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $taskRoot 'backend\src'
$env:TEMP = Join-Path $taskRoot 'tmp'
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path $taskRoot '.cache\pyinstaller'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
Copy-Item -LiteralPath packages\contracts\protocol.schema.json -Destination backend\src\studynote\ipc\protocol.schema.json
$taskSchema = Join-Path $taskRoot 'backend\src\studynote\ipc\protocol.schema.json'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --console --name studynote-backend --paths backend\src --add-data "$taskSchema;studynote/ipc" --distpath dist\sidecar --workpath build\sidecar --specpath build backend\sidecar.py
if ($LASTEXITCODE -ne 0) { throw 'Sidecar build failed.' }
Copy-Item -LiteralPath dist\sidecar\studynote-backend.exe -Destination apps\desktop\src-tauri\binaries\studynote-backend-x86_64-pc-windows-msvc.exe
& dist\sidecar\studynote-backend.exe --smoke-test --data-dir tmp\sidecar-smoke | Out-File -Encoding utf8 tmp\sidecar-smoke.json
if ($LASTEXITCODE -ne 0) { throw 'Packaged sidecar smoke test failed.' }
Write-Host 'Python sidecar packaged and verified.'
