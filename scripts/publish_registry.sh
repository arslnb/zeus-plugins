#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ZEUS_REGISTRY_OUTPUT_DIR:-$ROOT_DIR/dist/registry}"
PRIVATE_KEY_FILE="${ZEUS_REGISTRY_PRIVATE_KEY_FILE:-}"
PRIVATE_KEY_VALUE="${ZEUS_REGISTRY_PRIVATE_KEY:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -n "${ZEUS_REGISTRY_BASE_URL:-}" ]]; then
  BASE_URL="${ZEUS_REGISTRY_BASE_URL%/}"
elif [[ -n "${GITHUB_REPOSITORY:-}" ]]; then
  REPO_NAME="${GITHUB_REPOSITORY#*/}"
  OWNER="${GITHUB_REPOSITORY%%/*}"
  BASE_URL="https://${OWNER}.github.io/${REPO_NAME}"
else
  echo "ZEUS_REGISTRY_BASE_URL is required when not running in GitHub Actions" >&2
  exit 2
fi

TEMP_KEY_FILE=""
cleanup() {
  if [[ -n "$TEMP_KEY_FILE" && -f "$TEMP_KEY_FILE" ]]; then
    rm -f "$TEMP_KEY_FILE"
  fi
}
trap cleanup EXIT

if [[ -z "$PRIVATE_KEY_FILE" && -n "$PRIVATE_KEY_VALUE" ]]; then
  TEMP_KEY_FILE="$(mktemp "${TMPDIR:-/tmp}/zeus-registry-key.XXXXXX")"
  printf '%s' "$PRIVATE_KEY_VALUE" > "$TEMP_KEY_FILE"
  PRIVATE_KEY_FILE="$TEMP_KEY_FILE"
fi

if [[ -z "$PRIVATE_KEY_FILE" ]]; then
  echo "Set ZEUS_REGISTRY_PRIVATE_KEY_FILE or ZEUS_REGISTRY_PRIVATE_KEY before publishing" >&2
  exit 2
fi

CMD=(
  "$PYTHON_BIN" -m zeus_plugins.cli plugin publish "$ROOT_DIR"
  --output-dir "$OUTPUT_DIR"
  --base-url "$BASE_URL"
  --private-key "$PRIVATE_KEY_FILE"
  --clean
)

if [[ -n "${ZEUS_REGISTRY_PLUGIN_IDS:-}" ]]; then
  IFS=',' read -r -a plugin_ids <<< "$ZEUS_REGISTRY_PLUGIN_IDS"
  for plugin_id in "${plugin_ids[@]}"; do
    trimmed="$(printf '%s' "$plugin_id" | xargs)"
    if [[ -n "$trimmed" ]]; then
      CMD+=(--plugin-id "$trimmed")
    fi
  done
fi

(
  cd "$ROOT_DIR"
  PYTHONPATH=src "${CMD[@]}"
)
