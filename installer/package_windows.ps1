$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Liuant Windows packaging readiness (v0.6.0)"
Write-Host "=========================================="
python -m cli.liuant release-check
Write-Host ""
python -m cli.liuant desktop check
Write-Host ""

if (-not (Test-Path "apps/desktop/src-tauri")) {
  Write-Host "No Tauri desktop project found at apps/desktop/src-tauri."
  Write-Host "Create the Tauri project and install Node.js + Rust/Cargo before building .msi/.exe artifacts."
  exit 2
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  Write-Host "Rust/Cargo is required for Tauri packaging."
  Write-Host "Install from: https://rustup.rs"
  exit 2
}

if (Get-Command pnpm -ErrorAction SilentlyContinue) {
  Push-Location apps/desktop
  pnpm tauri build
  Pop-Location
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
  Push-Location apps/desktop
  npm run tauri:build
  Pop-Location
} else {
  Write-Host "Node.js package tooling is required: install pnpm or npm."
  exit 2
}

Write-Host ""
Write-Host "Running release checks..."
python -m cli.liuant release manifest
python -m cli.liuant release checksum

python -m cli.liuant release unsigned-build-check
Write-Host ""
Write-Host "========================================="
Write-Host "UNSIGNED BUILD SUMMARY"
Write-Host "========================================="
python -m cli.liuant release unsigned-artifacts
Write-Host ""
Write-Host "========================================="
Write-Host "Build report:"
python -m cli.liuant release build-report | Select-String -Pattern "path|status" | Select-Object -First 5
Write-Host "========================================="
Write-Host ""
Write-Host "Packaging complete. This is an UNSIGNED build."
Write-Host "Code signing remains pending."
Write-Host "No auto-publishing or cloud distribution is performed."
