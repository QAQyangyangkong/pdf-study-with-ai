param([string]$Executable = 'apps\desktop\src-tauri\target\release\studynote-desktop.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $taskRoot
$env:STUDYNOTE_DATA_DIR = Join-Path $taskRoot 'tmp\tauri-smoke'
$taskReport = Join-Path $taskRoot 'tmp\tauri-smoke.json'
New-Item -ItemType Directory -Force -Path $env:STUDYNOTE_DATA_DIR | Out-Null
if (Test-Path -LiteralPath $taskReport) { Remove-Item -LiteralPath $taskReport }
$taskExe = (Resolve-Path -LiteralPath $Executable).Path
$taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--smoke-test', '--report', 'tmp\tauri-smoke.json') -WindowStyle Hidden -PassThru
if (-not $taskProcess.WaitForExit(45000)) {
  $taskProcess.Kill()
  throw 'Native UI smoke test timed out.'
}
if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'Native UI smoke failed.' }
$taskResult = Get-Content -LiteralPath $taskReport -Raw | ConvertFrom-Json
if (-not $taskResult.ok -or -not $taskResult.frontend_ready) { throw 'Native UI report failed validation.' }
Write-Host 'React WebView → Rust IPC → packaged Python sidecar verified.'
