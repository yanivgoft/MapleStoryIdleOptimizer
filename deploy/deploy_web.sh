#!/usr/bin/env bash
# Build the static front end against a deployed API and publish it to a static host.
#
#   API_URL=https://msi-api-xxxx-uc.a.run.app STATIC_HOST=github-pages deploy/deploy_web.sh
#
# API_URL may be omitted if PROJECT_ID/REGION/SERVICE are set and gcloud is logged in (the URL is then read from Cloud Run).
# STATIC_HOST: github-pages (build with the right base path, then tells you to run the workflow) | cloudflare | firebase | none (build only).
# Accounts (optional, Google sign-in + cloud-saved profiles): the four VITE_FIREBASE_* variables (see web/.env.example) are baked in at build time like VITE_API_URL
#   - from the environment / deploy/.env or from web/.env.production.  Unset = the app is built exactly without accounts.  STATIC_HOST=firebase also deploys
#   deploy/firebase/firestore.rules (--only hosting,firestore:rules); FIREBASE_DEPLOY_RULES=0 deploys hosting only.
# Configuration: environment variables or deploy/.env (see deploy/.env.example).  VITE_API_URL is baked into the bundle at BUILD time:
# a bundle built without it silently talks to http://localhost:8000, which is why this script refuses to continue if the URL is missing
# from the built files.  DRY_RUN=1 builds nothing and prints what would run.
set -euo pipefail
# shellcheck source=deploy/_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
load_env_file

STATIC_HOST="${STATIC_HOST:-github-pages}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/web/dist}"

if [ -z "${API_URL:-}" ] && [ -n "${PROJECT_ID:-}" ] && command -v gcloud >/dev/null 2>&1 && [ "$DRY_RUN" != "1" ]; then
  log "API_URL not set: asking Cloud Run for ${SERVICE:-msi-api} in ${REGION:-us-central1} ..."
  API_URL="$(gcloud --project "$PROJECT_ID" run services describe "${SERVICE:-msi-api}" --region "${REGION:-us-central1}" --format 'value(status.url)')"
fi
require_var API_URL "the deployed API's base URL, e.g. https://msi-api-xxxx-uc.a.run.app (printed by deploy_api.sh)"
API_URL="${API_URL%/}"
case "$API_URL" in https://*) ;; http://localhost*|http://127.0.0.1*) log "WARNING: API_URL is a local address - fine for a rehearsal, useless when published" ;; *) die "API_URL must start with https://" ;; esac

case "$STATIC_HOST" in
  github-pages|none) BASE="${WEB_BASE:-/}" ;;  # a GitHub project site lives under /<repo>/ - set WEB_BASE=/<repo>/ ; custom domain / user site: /
  cloudflare|firebase) BASE="/" ;;
  *) die "STATIC_HOST must be github-pages, cloudflare, firebase or none (got '$STATIC_HOST')" ;;
esac
[[ "$BASE" == /* && "$BASE" == */ ]] || die "WEB_BASE must start and end with '/' (got '$BASE')"

BUILD_CMD="VITE_API_URL=$API_URL npm run build -- --base=$BASE"
if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN=1: would run in web/: npm ci (unless SKIP_INSTALL=1); $BUILD_CMD   (output: $OUT_DIR)"
  log "then publish with STATIC_HOST=$STATIC_HOST"
  if [ "$STATIC_HOST" = "firebase" ]; then
    if [ "${FIREBASE_DEPLOY_RULES:-1}" = "1" ]; then log "firebase deploy --only hosting,firestore:rules (FIREBASE_DEPLOY_RULES=0 for hosting only)"; else log "firebase deploy --only hosting"; fi
  fi
  exit 0
fi

require_cmd npm "install Node.js 20+ (CI uses 22)"
cd "$REPO_ROOT/web"
if [ "$SKIP_INSTALL" != "1" ]; then npm ci; fi
# `npm run build` = tsc --noEmit && vite build; npm appends "-- <args>" to the LAST command, i.e. to vite build.
if [ "$OUT_DIR" = "$REPO_ROOT/web/dist" ]; then
  VITE_API_URL="$API_URL" npm run build -- --base="$BASE"
else
  npm run typecheck && VITE_API_URL="$API_URL" npx vite build --base="$BASE" --outDir "$OUT_DIR" --emptyOutDir
fi
[ -f "$OUT_DIR/index.html" ] || die "build produced no $OUT_DIR/index.html"
grep -rqF "$API_URL" "$OUT_DIR/assets" || die "the API URL is not inside the built bundle - VITE_API_URL did not reach vite (or the front end reads a different variable)"
log "built $OUT_DIR against $API_URL (base $BASE)"
# accounts: say what was built (the SDK config is public; it is only a feature switch here)
if [ -n "${VITE_FIREBASE_API_KEY:-}" ] && [ -n "${VITE_FIREBASE_AUTH_DOMAIN:-}" ] && [ -n "${VITE_FIREBASE_PROJECT_ID:-}" ] && [ -n "${VITE_FIREBASE_APP_ID:-}" ]; then
  grep -rqF "$VITE_FIREBASE_PROJECT_ID" "$OUT_DIR/assets" || die "VITE_FIREBASE_* are set but the Firebase project id is not inside the built bundle - the accounts feature did not get built in"
  log "accounts: ENABLED in this build (Firebase project $VITE_FIREBASE_PROJECT_ID); remember the console steps in deploy/README.md section 'Accounts setup'"
elif [ -f "$REPO_ROOT/web/.env.production" ] && grep -q '^VITE_FIREBASE_' "$REPO_ROOT/web/.env.production"; then
  log "accounts: VITE_FIREBASE_* found in web/.env.production (used by vite build)"
else
  log "accounts: disabled in this build (no VITE_FIREBASE_* variables) - the app has no sign-in"
fi

case "$STATIC_HOST" in
  none)
    log "build only (STATIC_HOST=none)." ;;
  github-pages)
    cat >&2 <<MSG
[deploy] GitHub Pages is published by CI, not from a laptop: run the "Deploy" workflow (Actions tab -> Deploy -> Run workflow, web_target=github-pages).
[deploy] The built files are in $OUT_DIR if you want to inspect them.  CORS: the API must allow the page's ORIGIN (no path): https://<user>.github.io
MSG
    ;;
  cloudflare)
    require_var CF_PAGES_PROJECT "the Cloudflare Pages project name"
    if command -v npx >/dev/null 2>&1; then
      log "publishing to Cloudflare Pages project $CF_PAGES_PROJECT (needs 'npx wrangler login' or CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID) ..."
      npx --yes wrangler pages deploy "$OUT_DIR" --project-name "$CF_PAGES_PROJECT"
    else
      log "npx not found; upload $OUT_DIR in the Cloudflare dashboard (Workers & Pages -> Create -> Pages -> Upload assets)"
    fi
    log "CORS: the API must allow https://$CF_PAGES_PROJECT.pages.dev (and your custom domain, if any)" ;;
  firebase)
    require_var FIREBASE_PROJECT "the Firebase project ID"
    FB_DIR="$REPO_ROOT/deploy/firebase"
    rm -rf "$FB_DIR/public" && mkdir -p "$FB_DIR/public" && cp -R "$OUT_DIR"/. "$FB_DIR/public/"
    # hosting + the Firestore security rules (accounts); FIREBASE_DEPLOY_RULES=0 = hosting only (e.g. before the Firestore database exists)
    FB_ONLY="hosting"
    if [ "${FIREBASE_DEPLOY_RULES:-1}" = "1" ]; then FB_ONLY="hosting,firestore:rules"; fi
    if command -v npx >/dev/null 2>&1; then
      log "publishing to Firebase project $FIREBASE_PROJECT: --only $FB_ONLY (needs 'npx firebase-tools login'; the rules need the Firestore database to exist: deploy/README.md 'Accounts setup') ..."
      (cd "$FB_DIR" && npx --yes firebase-tools deploy --only "$FB_ONLY" --project "$FIREBASE_PROJECT")
    else
      log "npx not found; copy $FB_DIR to a machine with the Firebase CLI and run: firebase deploy --only $FB_ONLY --project $FIREBASE_PROJECT (from $FB_DIR)"
    fi
    log "CORS: the API must allow https://$FIREBASE_PROJECT.web.app and https://$FIREBASE_PROJECT.firebaseapp.com" ;;
esac
