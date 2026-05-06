$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

Write-Host ""
Write-Host "Magical PDF: preparing project for Codex on Windows" -ForegroundColor Green
Write-Host "Project folder: $projectRoot"
Write-Host ""

function Require-Command($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "$name is not available. $hint"
  }
}

Require-Command "git.exe" "Install Git: https://git-scm.com/download/win"
Require-Command "node.exe" "Install Node.js LTS: https://nodejs.org/"
Require-Command "npm.cmd" "Install Node.js LTS: https://nodejs.org/"

Write-Host "Switching to main..."
git switch main

Write-Host "Pulling latest changes from GitHub..."
git pull --ff-only origin main

Write-Host "Installing dependencies..."
npm.cmd ci

Write-Host ""
Write-Host "Ready." -ForegroundColor Green
Write-Host "Open Codex and choose this folder:"
Write-Host "$projectRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Suggested prompt for Codex:"
Write-Host "Продолжи работу над Magical PDF. Сначала проверь git status, затем помоги с задачей." -ForegroundColor Cyan
