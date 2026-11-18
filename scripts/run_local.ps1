# Run the Pasto Bacano Streamlit chat locally from PowerShell (SQLite, no production services).
# Same behaviour as scripts/run_local.sh: reads only GOOGLE_API_KEY and GEE_* from the env file.
#
# Usage: .\scripts\run_local.ps1 [-EnvFile .env] [-Port 8501] [-TestPicker]

param(
    [string]$EnvFile = ".env",
    [int]$Port = 8501,
    [switch]$TestPicker
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path $EnvFile)) {
    Write-Error "Env file not found: $EnvFile (see .env.example)"
}

function Read-Var([string]$Name) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$Name=", "").Trim().Trim('"').Trim("'")
}

$env:GOOGLE_API_KEY = Read-Var "GOOGLE_API_KEY"
$env:GEE_PROJECT = Read-Var "GEE_PROJECT"
$env:GEE_SERVICE_ACCOUNT = Read-Var "GEE_SERVICE_ACCOUNT"
$env:GEE_KEY_FILE = Read-Var "GEE_KEY_FILE"

$env:APP_ENV = "development"
$env:DATABASE_TYPE = "sqlite"
$env:PYTHONPATH = (Get-Location).Path
$env:SEMENTE_MANIFEST = "semente.yaml"
if ($TestPicker) { $env:PASTO10_TEST_PICKER = "1" }

uv run streamlit run app/streamlit_app.py --server.port $Port
