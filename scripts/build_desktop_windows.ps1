$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReportDir = Join-Path $RootDir "release"
$Report = Join-Path $ReportDir "build-report.json"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$missing = @()
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $missing += "node" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { $missing += "npm" }
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) { $missing += "rustc" }
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { $missing += "cargo" }
if (-not (Get-Command rustup -ErrorAction SilentlyContinue)) { $missing += "rustup" }

Write-Host "Liuant Windows desktop build helper"
Write-Host "This script does not change execution policy and does not sign installers."
if ($missing.Count -gt 0) {
  Write-Host "Missing dependencies: $($missing -join ', ')"
  Write-Host "Install Visual Studio Build Tools, WebView2 Runtime, Rust MSVC toolchain, and Node.js 20+ before native packaging."
}

Set-Location (Join-Path $RootDir "apps\desktop")
npm run typecheck
npm run build

$nativeStatus = "dependency_missing"
if ((Get-Command cargo -ErrorAction SilentlyContinue) -and (Get-Command rustc -ErrorAction SilentlyContinue)) {
  npm run tauri:build
  $nativeStatus = "tauri_build_attempted"
}

@{
  platform = "windows"
  frontend_build_status = "passed"
  native_build_status = $nativeStatus
  signed = $false
  notarized = $false
  missing = $missing
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $Report

Write-Host "Build report written to $Report"
