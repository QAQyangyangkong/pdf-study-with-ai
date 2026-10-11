param(
  [ValidateSet('portable', 'installer', 'all')][string]$Mode = 'all',
  [string]$OutputDirectory = $env:STUDYNOTE_RELEASE_DIR
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $taskRoot
if (-not $OutputDirectory) {
  $OutputDirectory = Join-Path (Split-Path $taskRoot -Parent) 'StudyNote'
  if ([IO.Path]::GetFullPath($OutputDirectory) -eq $taskRoot) {
    $OutputDirectory = Join-Path (Split-Path $taskRoot -Parent) 'StudyNote-release'
  }
}
$taskOutput = [IO.Path]::GetFullPath($OutputDirectory)
$taskRootPrefix = $taskRoot.TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
if ($taskOutput.Equals($taskRoot, [StringComparison]::OrdinalIgnoreCase) -or $taskOutput.StartsWith($taskRootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw 'Choose a release directory outside the source project.'
}
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskRelease = Join-Path $taskRoot 'apps\desktop\src-tauri\target\release'
$taskProgram = Join-Path $taskOutput 'StudyNote.exe'
$taskBackend = Join-Path $taskOutput 'studynote-backend.exe'
$taskStage = Join-Path $taskRoot 'scripts\release\stage_desktop.py'
$taskCargo = Join-Path $taskRoot '.cache\cargo\bin'
if (Test-Path -LiteralPath $taskCargo) {
  $env:CARGO_HOME = Join-Path $taskRoot '.cache\cargo'
  $env:RUSTUP_HOME = Join-Path $taskRoot '.cache\rustup'
  $env:PATH = "$taskCargo;$env:PATH"
}
if ($Mode -in @('portable', 'all')) {
  & (Join-Path $taskRoot 'scripts\check.ps1')
  & (Join-Path $PSScriptRoot 'sidecar.ps1')
  pnpm --filter @studynote/desktop tauri build --no-bundle -- --locked
  if ($LASTEXITCODE -ne 0) { throw 'Direct-launch desktop build failed.' }
  # No installer is involved yet, so place the sidecar beside the built GUI explicitly.
  Copy-Item -LiteralPath (Join-Path $taskRoot 'apps\desktop\src-tauri\binaries\studynote-backend-x86_64-pc-windows-msvc.exe') -Destination (Join-Path $taskRelease 'studynote-backend.exe') -Force
  & $taskPython $taskStage portable --source $taskRelease --output $taskOutput --readme (Join-Path $taskRoot 'README.md')
  if ($LASTEXITCODE -ne 0) { throw 'Direct-launch staging failed.' }
} elseif (-not (Test-Path -LiteralPath $taskProgram) -or -not (Test-Path -LiteralPath $taskBackend)) {
  throw 'Run pnpm build:portable before creating an installer.'
}
# Test the delivered files from their own directory before any installer exists.
& (Join-Path $taskRoot 'scripts\release\smoke.ps1') -Executable $taskProgram
& $taskPython (Join-Path $taskRoot 'scripts\release\verify_sidecar.py') $taskBackend (Join-Path $taskRoot 'tests\fixtures\sample.pdf')
if ($LASTEXITCODE -ne 0) { throw 'Delivered PDF and search verification failed.' }
if ($Mode -in @('installer', 'all')) {
  # Check the actual inputs used by NSIS, including Tauri's externalBin source.
  & $taskPython $taskStage verify --desktop (Join-Path $taskRelease 'studynote-desktop.exe') --backend (Join-Path $taskRoot 'apps\desktop\src-tauri\binaries\studynote-backend-x86_64-pc-windows-msvc.exe') --output $taskOutput
  if ($LASTEXITCODE -ne 0) { throw 'Installer inputs differ from the tested direct-launch version.' }
  pnpm --filter @studynote/desktop tauri bundle --bundles nsis --ci --no-binary-patching
  if ($LASTEXITCODE -ne 0) { throw 'Installer bundling failed.' }
  $taskConfig = Get-Content -LiteralPath (Join-Path $taskRoot 'apps\desktop\src-tauri\tauri.conf.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  $taskInstallerName = "$($taskConfig.productName)_$($taskConfig.version)_x64-setup.exe"
  $taskInstaller = Join-Path $taskRelease "bundle\nsis\$taskInstallerName"
  & $taskPython $taskStage installer --source $taskInstaller --output (Join-Path $taskOutput 'installers')
  if ($LASTEXITCODE -ne 0) { throw 'External installer staging failed.' }
  $taskPreviousRootInstaller = Join-Path $taskRoot $taskInstallerName
  if (Test-Path -LiteralPath $taskPreviousRootInstaller -PathType Leaf) {
    Remove-Item -LiteralPath $taskPreviousRootInstaller
  }
}
Write-Host "Windows release complete: $taskProgram"
