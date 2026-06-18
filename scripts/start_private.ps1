param(
    [string]$EnvFile = ".env.private"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python scripts\private_deploy_check.py --env-file $EnvFile
if ($LASTEXITCODE -ne 0) {
    throw "Private deployment configuration validation failed."
}

$env:TA_ENV_FILE = (Resolve-Path $EnvFile).Path
docker compose --env-file $EnvFile -f docker-compose.private.yml up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose startup failed."
}

Write-Host "TradingAgents-Astock started: http://localhost:8501"
