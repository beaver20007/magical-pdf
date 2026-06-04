#!/usr/bin/env bash
set -euo pipefail

PLUGINS=(
  "google-drive@openai-curated"
  "gmail@openai-curated"
  "google-calendar@openai-curated"
  "slack@openai-curated"
  "notion@openai-curated"
  "linear@openai-curated"
  "teams@openai-curated"
)

CODEX_HOME="${HOME}/.codex"
CONFIG_PATH="${CODEX_HOME}/config.toml"

echo "Codex global connector setup for macOS"
echo "Codex home: ${CODEX_HOME}"
echo "Config:     ${CONFIG_PATH}"
echo

mkdir -p "${CODEX_HOME}"
touch "${CONFIG_PATH}"

missing=()
for plugin in "${PLUGINS[@]}"; do
  if ! grep -Fq "[plugins.\"${plugin}\"]" "${CONFIG_PATH}"; then
    missing+=("${plugin}")
  fi
done

if [ "${#missing[@]}" -eq 0 ]; then
  echo "All requested plugin sections already exist."
else
  echo "Missing plugin sections:"
  for plugin in "${missing[@]}"; do
    echo " - ${plugin}"
  done

  timestamp="$(date +%Y%m%d-%H%M%S)"
  backup_path="${CONFIG_PATH}.bak-${timestamp}"
  cp "${CONFIG_PATH}" "${backup_path}"
  echo
  echo "Backup created: ${backup_path}"

  {
    echo
    for plugin in "${missing[@]}"; do
      echo "[plugins.\"${plugin}\"]"
      echo "enabled = true"
      echo
    done
  } >> "${CONFIG_PATH}"

  echo "Plugin sections added."
fi

echo
echo "Next steps:"
echo "1. Restart Codex."
echo "2. Open Codex settings -> Connectors."
echo "3. Authorize Google, Slack, Notion, Linear, and Teams if Codex asks."
echo "4. Run ./scripts/verify-codex-connectors-macos.sh"
