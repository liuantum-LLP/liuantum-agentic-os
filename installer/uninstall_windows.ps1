$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Stopping Liuant local server if it is running..."
try { .\liuant stop } catch { Write-Host "Server was not running or CLI was unavailable." }

Write-Host "Removing local virtual environment only. Workspace, .env, backups, and outputs are preserved."
if (Test-Path ".venv") {
  Remove-Item ".venv" -Recurse -Force
}

Write-Host "Uninstall complete. To remove user data manually, inspect workspace/ first."
