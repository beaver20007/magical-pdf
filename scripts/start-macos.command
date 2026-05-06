#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo
echo "Magical PDF: preparing project for Codex on macOS"
echo "Project folder: $PROJECT_ROOT"
echo

require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "$name is not available. $hint" >&2
    exit 1
  fi
}

require_command git "Install Git or Xcode Command Line Tools."
require_command node "Install Node.js LTS: https://nodejs.org/"
require_command npm "Install Node.js LTS: https://nodejs.org/"

echo "Switching to main..."
git switch main

echo "Pulling latest changes from GitHub..."
git pull --ff-only origin main

echo "Installing dependencies..."
npm ci

echo
echo "Ready."
echo "Open Codex and choose this folder:"
echo "$PROJECT_ROOT"
echo
echo "Suggested prompt for Codex:"
echo "Продолжи работу над Magical PDF. Сначала проверь git status, затем помоги с задачей."
