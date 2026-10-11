param([string]$Executable = 'apps\desktop\src-tauri\target\release\studynote-desktop.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $taskRoot
$taskDataDirectory = Join-Path $taskRoot 'tmp\tauri-smoke'
$taskReport = Join-Path $taskRoot 'tmp\tauri-smoke.json'
New-Item -ItemType Directory -Force -Path $taskDataDirectory | Out-Null
if (Test-Path -LiteralPath $taskReport) { Remove-Item -LiteralPath $taskReport }
$taskExe = (Resolve-Path -LiteralPath $Executable).Path
$taskPreviousDataDirectory = $env:STUDYNOTE_DATA_DIR
$taskPreviousPythonPath = $env:PYTHONPATH
try {
  $env:STUDYNOTE_DATA_DIR = $taskDataDirectory
  Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
  $taskArguments = '--smoke-test --report "{0}"' -f $taskReport
  $taskProcess = Start-Process -FilePath $taskExe -WorkingDirectory (Split-Path $taskExe -Parent) -ArgumentList $taskArguments -WindowStyle Hidden -PassThru
  if (-not $taskProcess.WaitForExit(45000)) {
    $taskProcess.Kill()
    throw 'Native UI smoke test timed out.'
  }
  if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'Native UI smoke failed.' }
  $taskResult = Get-Content -LiteralPath $taskReport -Raw | ConvertFrom-Json
  if (-not $taskResult.ok -or -not $taskResult.frontend_ready -or $taskResult.workspace.schema_version -ne 3) { throw 'Native UI report failed validation.' }
} finally {
  if ($null -eq $taskPreviousDataDirectory) { Remove-Item Env:STUDYNOTE_DATA_DIR -ErrorAction SilentlyContinue }
  else { $env:STUDYNOTE_DATA_DIR = $taskPreviousDataDirectory }
  if ($null -eq $taskPreviousPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
  else { $env:PYTHONPATH = $taskPreviousPythonPath }
}
Write-Host 'React WebView, Rust IPC and packaged Python schema v3 verified.'
