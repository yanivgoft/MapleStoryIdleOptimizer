#!/usr/bin/env bash
# Build the API container with Cloud Build and deploy it to Cloud Run (stateless, scale-to-zero, capped).
#
#   PROJECT_ID=my-proj CORS_ORIGINS=https://me.github.io deploy/deploy_api.sh
#
# Configuration: environment variables or deploy/.env (see deploy/.env.example).  DRY_RUN=1 stages the build context and prints
# the exact gcloud commands without calling Google.  Prints the service URL (last line: API_URL=...) and, under GitHub Actions,
# writes api_url to $GITHUB_OUTPUT.
set -euo pipefail
# shellcheck source=deploy/_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
load_env_file

require_var PROJECT_ID "the Google Cloud project ID"
require_var CORS_ORIGINS "origin(s) of the web front end, e.g. https://<user>.github.io"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-msi-api}"
PROXY_HOPS="${PROXY_HOPS:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
CONCURRENCY="${CONCURRENCY:-10}"
CPU="${CPU:-1}"
MEMORY="${MEMORY:-512Mi}"
TIMEOUT="${TIMEOUT:-60}"
RATE_LIMIT_PER_MINUTE="${RATE_LIMIT_PER_MINUTE:-120}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
ENABLE_APIS="${ENABLE_APIS:-0}"
SMOKE="${SMOKE:-0}"
DRY_RUN="${DRY_RUN:-0}"

[[ "$PROXY_HOPS" =~ ^[0-9]+$ ]] || die "PROXY_HOPS must be a non-negative integer"
[[ "$MAX_INSTANCES" =~ ^[0-9]+$ ]] && [ "$MAX_INSTANCES" -ge 1 ] || die "MAX_INSTANCES must be >= 1 (it is the spending cap)"
case "$CORS_ORIGINS" in
  *'*'*) log "WARNING: CORS_ORIGINS contains '*' - any website may call your API from a browser" ;;
  *"/ "*|*"/,"*|*/) die "CORS_ORIGINS entries must not end with '/' (an origin has no path)" ;;
esac
if [ "$DRY_RUN" != "1" ]; then require_cmd gcloud "install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install"; fi

# ---------------------------------------------------------------------------------------------------------------------------
# 1. Stage a minimal build context.  `gcloud ... --source` uploads the directory it is given (honouring .gcloudignore, NOT
#    api/Dockerfile.dockerignore) and only looks for a Dockerfile at its root, whereas api/Dockerfile expects the repository layout
#    and lives in api/.  So: copy exactly what the Dockerfile COPYs into a temp dir, with the Dockerfile at its root.  (Uploading the
#    repo root as-is would ship .venv/, web/node_modules/, the workbooks ... hundreds of MB.)
# ---------------------------------------------------------------------------------------------------------------------------
DOCKERFILE="${DOCKERFILE:-$REPO_ROOT/api/Dockerfile}"     # (override only to test a modified Dockerfile)
[ -f "$DOCKERFILE" ] || die "$DOCKERFILE not found"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/msi-api-stage.XXXXXX")"
ENV_FILE=""
cleanup() { [ -z "$ENV_FILE" ] || rm -f "$ENV_FILE"; [ "${KEEP_STAGE:-0}" = "1" ] || rm -rf "$STAGE"; }
trap cleanup EXIT

cd "$REPO_ROOT"
mkdir -p "$STAGE/api" "$STAGE/src" "$STAGE/data"
cp api/*.py api/requirements.txt "$STAGE/api/"            # every API module (tests/ is a subdirectory and is not copied)
cp -R engine "$STAGE/engine"
for f in companion_kits.py companion_python_model.py status_timeline.py; do cp "src/$f" "$STAGE/src/$f"; done
cp data/factor_table.json "$STAGE/data/"
if [ -f data/cube_potential_data.json ]; then cp data/cube_potential_data.json "$STAGE/data/"; fi
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$STAGE" -name '*.pyc' -delete
cp "$DOCKERFILE" "$STAGE/Dockerfile"

# Guard against drift: every source the Dockerfile COPYs must exist in the stage, and a cube optimiser must have its data.
awk '/^COPY[[:space:]]/ { for (i = 2; i < NF; i++) if ($i !~ /^--/) print $i }' "$DOCKERFILE" | while read -r src; do
  [ -e "$STAGE/${src%/}" ] || { echo "[deploy] ERROR: api/Dockerfile COPYs '$src' but the staging step does not provide it - update deploy/deploy_api.sh" >&2; exit 1; }
done
for m in api/*.py; do                                       # an API module the Dockerfile forgets would crash the container at import time
  grep -q "api/$(basename "$m")" "$DOCKERFILE" || die "$m is not in api/Dockerfile's COPY list (the container would fail to import it) - add it to the Dockerfile"
done
if [ -f engine/cubes.py ] && ! grep -q 'cube_potential_data' "$DOCKERFILE"; then
  die "engine/cubes.py exists but api/Dockerfile does not COPY data/cube_potential_data.json - the container would fail at runtime. Add the COPY line (the staging step already ships the file)."
fi
log "staged build context: $(du -sk "$STAGE" | cut -f1) KiB in $STAGE"

# ---------------------------------------------------------------------------------------------------------------------------
# 2. Environment for the service, via an env-vars file (commas inside MSI_CORS_ORIGINS would break `--set-env-vars`).
# ---------------------------------------------------------------------------------------------------------------------------
ENV_FILE="$(mktemp "${TMPDIR:-/tmp}/msi-api-env.XXXXXX")"   # outside the staged build context: it never reaches the image or the upload
cat > "$ENV_FILE" <<YAML
MSI_CORS_ORIGINS: "${CORS_ORIGINS}"
MSI_PROXY_HOPS: "${PROXY_HOPS}"
MSI_RATE_LIMIT_PER_MINUTE: "${RATE_LIMIT_PER_MINUTE}"
MSI_LOG_LEVEL: "${LOG_LEVEL}"
YAML
# Any other MSI_* variable exported in the environment / deploy/.env (e.g. MSI_SENS_TIMEOUT_S, MSI_RATE_LIMIT_SENS_PER_MIN, MSI_MAX_BODY_BYTES)
# is passed through to the service unchanged - EXCEPT MSI_INCLUDE_UNPUBLISHED: the publish gate (classes with PUBLISHED = False stay off the live site) must never be
# opened by a stray variable of the deploying shell.
while IFS= read -r name; do
  case "$name" in MSI_CORS_ORIGINS|MSI_PROXY_HOPS|MSI_RATE_LIMIT_PER_MINUTE|MSI_LOG_LEVEL) continue ;;
    MSI_INCLUDE_UNPUBLISHED) log "ignoring MSI_INCLUDE_UNPUBLISHED from the environment: never deployed (unpublished classes stay off the live site)"; continue ;; esac
  printf '%s: "%s"\n' "$name" "${!name}" >> "$ENV_FILE"
done < <(compgen -e | grep '^MSI_' || true)

GCLOUD=(gcloud --project "$PROJECT_ID")
DEPLOY_CMD=("${GCLOUD[@]}" run deploy "$SERVICE"
  --source "$STAGE"
  --region "$REGION"
  --platform managed
  --allow-unauthenticated
  --max-instances "$MAX_INSTANCES"
  --min-instances "$MIN_INSTANCES"
  --concurrency "$CONCURRENCY"
  --cpu "$CPU"
  --memory "$MEMORY"
  --timeout "$TIMEOUT"
  --env-vars-file "$ENV_FILE"
  --quiet)

if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN=1: nothing is sent to Google.  Staged files:"
  (cd "$STAGE" && find . -type f | sort | sed 's/^/    /') >&2
  log "env file:"; sed 's/^/    /' "$ENV_FILE" >&2
  [ "$ENABLE_APIS" = "1" ] && log "would run: ${GCLOUD[*]} services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com"
  log "would run: ${DEPLOY_CMD[*]}"
  log "would run: ${GCLOUD[*]} run services describe $SERVICE --region $REGION --format value(status.url)"
  exit 0
fi

# ---------------------------------------------------------------------------------------------------------------------------
# 3. Deploy.
# ---------------------------------------------------------------------------------------------------------------------------
if [ "$ENABLE_APIS" = "1" ]; then
  log "enabling APIs (run, artifactregistry, cloudbuild) ..."
  "${GCLOUD[@]}" services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
fi

log "deploying $SERVICE to $PROJECT_ID/$REGION (max-instances=$MAX_INSTANCES, concurrency=$CONCURRENCY, cpu=$CPU, memory=$MEMORY, min-instances=$MIN_INSTANCES) ..."
"${DEPLOY_CMD[@]}"

URL="$("${GCLOUD[@]}" run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
[ -n "$URL" ] || die "deployed, but could not read the service URL"
log "deployed: $URL"
if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "api_url=$URL" >> "$GITHUB_OUTPUT"; fi

if [ "$SMOKE" = "1" ]; then
  log "running the smoke test ..."
  API_URL="$URL" SMOKE_ORIGIN="${CORS_ORIGINS%%,*}" "$DEPLOY_DIR/smoke_test.sh"
fi
cat >&2 <<MSG
[deploy] next: (1) build the front end with VITE_API_URL=$URL (deploy/deploy_web.sh),
[deploy]       (2) verify MSI_PROXY_HOPS=$PROXY_HOPS is right for Cloud Run (deploy/README.md section 6).
MSG
echo "API_URL=$URL"
