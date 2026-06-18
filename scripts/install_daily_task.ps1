param(
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time = "18:30",
    [ValidatePattern('^\d{6}(,\d{6})*$')]
    [string]$Tickers = "600519",
    [ValidateSet("brief", "full", "risk")]
    [string]$Template = "brief"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DesktopExe = Join-Path $Root "TradingAgents-Astock.exe"

if (Test-Path $DesktopExe) {
    & $DesktopExe --daily-report --tickers $Tickers --template $Template --save-config --configure-only
    $TaskCommand = "`"$DesktopExe`" --daily-report"
} else {
    $Python = (Get-Command python -ErrorAction Stop).Source
    Push-Location $Root
    try {
        & $Python -m tradingagents.reporting.daily --tickers $Tickers --template $Template --save-config --configure-only
    } finally {
        Pop-Location
    }
    $TaskCommand = "`"$Python`" -m tradingagents.reporting.daily"
}

schtasks.exe /Create /TN "TradingAgents-Astock-Daily" /TR $TaskCommand /SC DAILY /ST $Time /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the Windows scheduled task. Exit code: $LASTEXITCODE"
}

Write-Host "Created TradingAgents-Astock-Daily. Run time: $Time."
