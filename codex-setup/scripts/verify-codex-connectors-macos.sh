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

CONFIG_PATH="${HOME}/.codex/config.toml"

echo "Codex connector config verification for macOS"
echo "Config: ${CONFIG_PATH}"
echo

if [ ! -f "${CONFIG_PATH}" ]; then
  echo "config.toml was not found."
  exit 1
fi

all_ok=1
for plugin in "${PLUGINS[@]}"; do
  if ! grep -Fq "[plugins.\"${plugin}\"]" "${CONFIG_PATH}"; then
    echo "[missing]  ${plugin}"
    all_ok=0
    continue
  fi

  if awk -v section="[plugins.\"${plugin}\"]" '
    $0 == section { in_section=1; found=0; next }
    in_section && /^\[/ { exit found ? 0 : 1 }
    in_section && /^enabled[[:space:]]*=[[:space:]]*true[[:space:]]*$/ { found=1 }
    END { if (in_section && found) exit 0; if (in_section) exit 1 }
  ' "${CONFIG_PATH}"; then
    echo "[enabled]  ${plugin}"
  else
    echo "[disabled] ${plugin}"
    all_ok=0
  fi
done

echo
if [ "${all_ok}" -eq 1 ]; then
  echo "All requested plugin sections are enabled globally."
  echo "Restart Codex and complete OAuth authorization in Connectors settings if needed."
  exit 0
fi

echo "Some plugins are missing or disabled. Run ./scripts/setup-codex-connectors-macos.sh"
exit 2
