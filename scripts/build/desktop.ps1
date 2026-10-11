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
$taskConfig = Get-Content -LiteralPath (Join-Path $taskRoot 'apps\desktop\src-tauri\tauri.conf.json') -Raw | ConvertFrom-Json
$taskInstallerName = "$($taskConfig.productName)_$($taskConfig.version)_x64-setup.exe"
$taskInstaller = Join-Path $taskRoot "apps\desktop\src-tauri\target\release\bundle\nsis\$taskInstallerName"
$taskConvenientInstaller = Join-Path $taskRoot $taskInstallerName
Copy-Item -LiteralPath $taskInstaller -Destination $taskConvenientInstaller -Force
Write-Host "Installer copied to: $taskConvenientInstaller"
Write-Host 'Tauri Windows build complete.'
