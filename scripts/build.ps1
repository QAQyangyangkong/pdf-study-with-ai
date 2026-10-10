param([switch]$Installer)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskTemp = Join-Path $taskRoot 'tmp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = Join-Path $taskRoot 'src'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $taskRoot '.cache\pyinstaller'
& (Join-Path $PSScriptRoot 'check.ps1')
& $taskPython -m PyInstaller --noconfirm packaging\StudyDesk.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
$taskExecutable = Join-Path $taskRoot 'dist\StudyDesk\StudyDesk.exe'
$taskReport = Join-Path $taskTemp 'packaged-smoke.json'
if (Test-Path -LiteralPath $taskReport) { Remove-Item -LiteralPath $taskReport }
$taskProcess = Start-Process -FilePath $taskExecutable -ArgumentList @('--smoke-test', '--data-dir', 'tmp\packaged-smoke', '--report', 'tmp\packaged-smoke.json') -WindowStyle Hidden -PassThru
if (-not $taskProcess.WaitForExit(30000)) {
    $taskProcess.Kill()
    throw 'Packaged UI smoke test timed out.'
}
if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'Packaged UI smoke test failed.' }
$taskResult = Get-Content -LiteralPath $taskReport -Raw | ConvertFrom-Json
if (-not $taskResult.ok) { throw 'Packaged smoke report is invalid.' }
Compress-Archive -LiteralPath (Join-Path $taskRoot 'dist\StudyDesk') -DestinationPath (Join-Path $taskRoot 'dist\StudyDesk-0.1.0-windows-x64.zip') -Force
if ($Installer) {
    $taskCompiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $taskCompilerPath = if ($taskCompiler) { $taskCompiler.Source } else { Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe' }
    if (-not (Test-Path -LiteralPath $taskCompilerPath)) { throw 'Install Inno Setup 6 before building the installer.' }
    & $taskCompilerPath packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
}
Write-Host "Verified portable app: $taskExecutable"
