$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $taskRoot
$taskCargo = Join-Path $taskRoot '.cache\cargo\bin'
if (Test-Path -LiteralPath $taskCargo) {
  $env:CARGO_HOME = Join-Path $taskRoot '.cache\cargo'
  $env:RUSTUP_HOME = Join-Path $taskRoot '.cache\rustup'
  $env:PATH = "$taskCargo;$env:PATH"
}
& (Join-Path $taskRoot 'scripts\check.ps1')
& (Join-Path $PSScriptRoot 'sidecar.ps1')
pnpm --filter @studynote/desktop tauri build -- --locked
if ($LASTEXITCODE -ne 0) { throw 'Tauri build failed.' }
& (Join-Path $taskRoot 'scripts\release\smoke.ps1')
Write-Host 'Tauri Windows build complete.'
