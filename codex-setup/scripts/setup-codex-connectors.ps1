param(
    [switch]$WhatIfOnly
)

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

$codexHome = Join-Path $env:USERPROFILE ".codex"
$configPath = Join-Path $codexHome "config.toml"

Write-Host "Codex global connector setup" -ForegroundColor Cyan
Write-Host "Codex home: $codexHome"
Write-Host "Config:     $configPath"
Write-Host ""

if (-not (Test-Path -LiteralPath $codexHome)) {
    New-Item -ItemType Directory -Path $codexHome | Out-Null
    Write-Host "Created Codex home folder."
}

if (-not (Test-Path -LiteralPath $configPath)) {
    if ($WhatIfOnly) {
        Write-Host "Would create config.toml"
    } else {
        New-Item -ItemType File -Path $configPath | Out-Null
        Write-Host "Created config.toml"
    }
}

$content = ""
if (Test-Path -LiteralPath $configPath) {
    $content = Get-Content -LiteralPath $configPath -Raw
}

$missing = New-Object System.Collections.Generic.List[string]

foreach ($plugin in $plugins) {
    $escaped = [regex]::Escape($plugin)
    $pattern = "(?m)^\[plugins\.""$escaped""\]"
    if ($content -notmatch $pattern) {
        $missing.Add($plugin)
    }
}

if ($missing.Count -eq 0) {
    Write-Host "All requested plugin sections already exist." -ForegroundColor Green
} else {
    Write-Host "Missing plugin sections:" -ForegroundColor Yellow
    foreach ($plugin in $missing) {
        Write-Host " - $plugin"
    }

    if ($WhatIfOnly) {
        Write-Host ""
        Write-Host "WhatIfOnly mode: no files changed."
        exit 0
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "$configPath.bak-$timestamp"
    Copy-Item -LiteralPath $configPath -Destination $backupPath
    Write-Host ""
    Write-Host "Backup created: $backupPath"

    $append = New-Object System.Text.StringBuilder
    if ($content.Trim().Length -gt 0) {
        [void]$append.AppendLine("")
    }

    foreach ($plugin in $missing) {
        [void]$append.AppendLine("[plugins.""$plugin""]")
        [void]$append.AppendLine("enabled = true")
        [void]$append.AppendLine("")
    }

    Add-Content -LiteralPath $configPath -Value $append.ToString().TrimEnd()
    Write-Host "Plugin sections added." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart Codex."
Write-Host "2. Open Codex settings -> Connectors."
Write-Host "3. Authorize Google, Slack, Notion, Linear, and Teams if Codex asks."
Write-Host "4. Run .\scripts\verify-codex-connectors.ps1"
