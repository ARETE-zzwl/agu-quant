param(
    [string]$Version = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Version) {
    $Version = python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:[-+].*)?$') {
    throw "Version must use major.minor.patch format: $Version"
}

if (-not $SkipTests) {
    python -m pytest tests -q
}

python -m PyInstaller --noconfirm --clean Agu.spec

$StageName = "TradingAgents-Astock-$Version-windows-x64"
$ZipPath = Join-Path $Root "dist\$StageName.zip"

Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
$PackageDir = Join-Path $Root "dist\TradingAgents-Astock"
Copy-Item "README.md", ".env.example", "LICENSE" $PackageDir
Copy-Item "docs\COMMERCIALIZATION.md" $PackageDir
$PackageScriptsDir = Join-Path $PackageDir "scripts"
New-Item -ItemType Directory -Path $PackageScriptsDir -Force | Out-Null
Copy-Item "scripts\install_daily_task.ps1" $PackageScriptsDir

Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal

$GithubBase = "https://github.com/simonlin1212/TradingAgents-astock/releases/download/v$Version"
python scripts\release_manifest.py `
    --artifact $ZipPath `
    --version $Version `
    --github-base-url $GithubBase `
    --mirror-base-url $env:TA_MIRROR_PUBLIC_BASE_URL `
    --output "dist\release-manifest.json"

Write-Host "Windows release created: $ZipPath"
Write-Host "Manifest created: dist\release-manifest.json"
