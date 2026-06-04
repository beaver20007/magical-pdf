$ErrorActionPreference = "Stop"

$plugins = @(
    "google-drive@openai-curated",
    "gmail@openai-curated",
    "google-calendar@openai-curated",
    "slack@openai-curated",
    "notion@openai-curated",
    "linear@openai-curated",
    "teams@openai-curated"
)

$configPath = Join-Path (Join-Path $env:USERPROFILE ".codex") "config.toml"

Write-Host "Codex connector config verification" -ForegroundColor Cyan
Write-Host "Config: $configPath"
Write-Host ""

if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Host "config.toml was not found." -ForegroundColor Red
    exit 1
}

$content = Get-Content -LiteralPath $configPath -Raw
$allOk = $true

foreach ($plugin in $plugins) {
    $escaped = [regex]::Escape($plugin)
    $sectionPattern = "(?ms)^\[plugins\.""$escaped""\]\s*.*?(?=^\[|\z)"
    $match = [regex]::Match($content, $sectionPattern)

    if (-not $match.Success) {
        Write-Host "[missing]  $plugin" -ForegroundColor Red
        $allOk = $false
        continue
    }

    if ($match.Value -match "(?m)^enabled\s*=\s*true\s*$") {
        Write-Host "[enabled]  $plugin" -ForegroundColor Green
    } else {
        Write-Host "[disabled] $plugin" -ForegroundColor Yellow
        $allOk = $false
    }
}

Write-Host ""

if ($allOk) {
    Write-Host "All requested plugin sections are enabled globally." -ForegroundColor Green
    Write-Host "Restart Codex and complete OAuth authorization in Connectors settings if needed."
    exit 0
}

Write-Host "Some plugins are missing or disabled. Run .\scripts\setup-codex-connectors.ps1" -ForegroundColor Yellow
exit 2
