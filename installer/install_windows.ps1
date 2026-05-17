param()

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Installing Liuant Agentic OS for Windows..."
python -c "import sys; raise SystemExit('Python 3.11 or newer is required.') if sys.version_info < (3, 11) else None"

python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .

New-Item -ItemType Directory -Force -Path workspace\outputs, workspace\backups, workspace\logs, workspace\security | Out-Null
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example. Add your own provider keys when ready."
} else {
  Write-Host ".env already exists or .env.example is missing; not overwriting."
}

.\liuant repair
.\liuant doctor

Write-Host "Next steps:"
Write-Host "  .\liuant auth token"
Write-Host "  .\liuant start"
Write-Host "  .\liuant open"
