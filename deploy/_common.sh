# Shared helpers, sourced by deploy_api.sh / deploy_web.sh / smoke_test.sh.  Not meant to be run directly.
# shellcheck shell=bash

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"

log() { printf '[deploy] %s\n' "$*" >&2; }
die() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

# Read KEY=VALUE lines from deploy/.env (if present) WITHOUT overriding variables that are already set in the
# environment, so `REGION=europe-west1 deploy/deploy_api.sh` beats the file.  Only a plain KEY=VALUE subset is
# understood (optional surrounding single/double quotes, '#' comment lines); the file is never executed.
load_env_file() {
  local f="${1:-$DEPLOY_DIR/.env}" line key val
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$val" =~ ^\"(.*)\"$ ]] || [[ "$val" =~ ^\'(.*)\'$ ]]; then val="${BASH_REMATCH[1]}"; fi
    if [ -z "${!key+x}" ]; then export "$key=$val"; fi
  done < "$f"
}

require_var() {   # require_var NAME "hint"
  local name="$1" hint="${2:-}"
  [ -n "${!name:-}" ] || die "$name is not set${hint:+ ($hint)}; set it in the environment or in deploy/.env (see deploy/.env.example)"
}

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "'$1' not found on PATH${2:+ ($2)}"; }
