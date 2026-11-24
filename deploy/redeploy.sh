#!/usr/bin/env bash
# One command to redeploy EVERYTHING and verify each step: local tests -> API (Cloud Run) -> API smoke test -> web page (Firebase Hosting) + Firestore rules
# -> live-site checks.  It stops at the first failing step and says which one and what to look at.
#
#   deploy/redeploy.sh                 # asks for a yes/no after showing the plan
#   deploy/redeploy.sh --yes           # no question
#   deploy/redeploy.sh --skip-tests    # skip the (about 90 s) local regression run
#   deploy/redeploy.sh --api-only | --web-only | --no-rules
#   deploy/redeploy.sh --dry-run       # builds / stages everything, sends nothing to Google
#
# Defaults are this project's (override with environment variables or deploy/.env): PROJECT_ID=maplestoryidleoptimizer, REGION=us-central1, SERVICE=msi-api,
# FIREBASE_PROJECT=$PROJECT_ID, CORS_ORIGINS=https://$FIREBASE_PROJECT.web.app,https://$FIREBASE_PROJECT.firebaseapp.com.  The web build reads the public Firebase
# config from web/.env.production (accounts feature).  Needs: gcloud (logged in), Node/npm + `npx firebase-tools login`, Python 3.11, curl.
# Exit code: 0 = everything deployed AND verified, 1 = a step failed, 2 = bad usage / missing tool / not logged in.
set -uo pipefail
# shellcheck source=deploy/_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
load_env_file
unset MSI_INCLUDE_UNPUBLISHED   # the publish gate: this script deploys PUBLISHED classes only (tests/run_all.py sets the variable itself for its own processes)

ASSUME_YES=0; SKIP_TESTS=0; API_ONLY=0; WEB_ONLY=0; NO_RULES=0; DRY_RUN="${DRY_RUN:-0}"
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1 ;; --skip-tests) SKIP_TESTS=1 ;; --api-only) API_ONLY=1 ;; --web-only) WEB_ONLY=1 ;;
    --no-rules) NO_RULES=1 ;; --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done
[ "$API_ONLY" = 1 ] && [ "$WEB_ONLY" = 1 ] && { echo "--api-only and --web-only exclude each other" >&2; exit 2; }

PROJECT_ID="${PROJECT_ID:-maplestoryidleoptimizer}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-msi-api}"
FIREBASE_PROJECT="${FIREBASE_PROJECT:-$PROJECT_ID}"
SITE_URL="https://${FIREBASE_PROJECT}.web.app"
CORS_ORIGINS="${CORS_ORIGINS:-https://${FIREBASE_PROJECT}.web.app,https://${FIREBASE_PROJECT}.firebaseapp.com}"
PY="${PYTHON:-python3}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/msi-redeploy.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cd "$REPO_ROOT" || exit 2

N=0; TOTAL=0; STEP=""
step() { N=$((N + 1)); STEP="$*"; HINT=""; printf '\n==> [%d/%d] %s\n' "$N" "$TOTAL" "$*"; }
ok()   { printf '    ok: %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*"; }
fail() { printf '\n!!  FAILED at step %d/%d (%s): %s\n' "$N" "$TOTAL" "$STEP" "$*" >&2; [ -z "${HINT:-}" ] || printf '    hint: %s\n' "$HINT" >&2
         printf '    Nothing after this step was run. Fix the problem and run deploy/redeploy.sh again (earlier steps are safe to repeat).\n' >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || { printf 'missing tool: %s%s\n' "$1" "${2:+ ($2)}" >&2; exit 2; }; }

WANT_TESTS=$((1 - SKIP_TESTS)); WANT_API=$((1 - WEB_ONLY)); WANT_WEB=$((1 - API_ONLY))
TOTAL=$((1 + WANT_TESTS + 2 * WANT_API + WANT_WEB + 1))      # preflight, tests, (deploy + smoke), web deploy, live checks
[ "$DRY_RUN" = 1 ] && printf 'DRY RUN: nothing is sent to Google, and the live checks are skipped.\n'

# --------------------------------------------------------------------------------------------------------------------------- 1. preflight
step "Preflight (tools, logins, git state)"
need git; need "$PY" "Python 3.11"; need curl
[ "$WANT_API" = 1 ] && need gcloud "https://cloud.google.com/sdk/docs/install"
[ "$WANT_WEB" = 1 ] && { need npm "Node.js 20+"; need npx; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' \
  || { HINT="the engine tests need Python 3.11: PYTHON=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 deploy/redeploy.sh"; fail "$PY is not Python 3.11"; }
ok "tools found, Python 3.11"
if [ "$WANT_API" = 1 ]; then
  ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)"
  if [ -z "$ACCOUNT" ]; then
    if [ "$DRY_RUN" = 1 ]; then warn "gcloud is not logged in (a real run needs: gcloud auth login)"; else HINT="run: gcloud auth login"; fail "gcloud is not logged in"; fi
  else
    ok "gcloud account: $ACCOUNT"
    if [ "$DRY_RUN" != 1 ]; then
      FOUND="$(gcloud projects describe "$PROJECT_ID" --format='value(projectId)' 2>"$TMP/gcloud_err")"
      [ "$FOUND" = "$PROJECT_ID" ] || { HINT="gcloud said: $(head -c 300 "$TMP/gcloud_err" | tr '\n' ' ')  | if it asks for new credentials run: gcloud auth login; otherwise check PROJECT_ID and the account (gcloud config set account ...)"; fail "cannot access Google Cloud project '$PROJECT_ID'"; }
      ok "project $PROJECT_ID is reachable"
    fi
  fi
fi
if [ "$WANT_WEB" = 1 ] && [ "$DRY_RUN" != 1 ]; then
  FB_LOGIN="$(cd "$DEPLOY_DIR/firebase" && npx --yes firebase-tools login:list 2>&1 || true)"
  case "$FB_LOGIN" in *@*) ok "firebase login: $(printf '%s' "$FB_LOGIN" | grep -o '[^ ]*@[^ ]*' | head -1)" ;;
    *) HINT="run: cd deploy/firebase && npx firebase-tools login"; fail "not logged in to Firebase" ;; esac
fi
[ -f web/.env.production ] && grep -q '^VITE_FIREBASE_PROJECT_ID=' web/.env.production && ok "accounts config found in web/.env.production" \
  || warn "web/.env.production has no VITE_FIREBASE_* values: the page will be built WITHOUT accounts"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; SHA="$(git rev-parse --short HEAD 2>/dev/null)"
DIRTY="$(git status --porcelain 2>/dev/null | grep -v '^??' | wc -l | tr -d ' ')"
ok "git: $BRANCH @ $SHA, $DIRTY modified tracked file(s)"
[ "$DIRTY" != 0 ] && warn "you are deploying uncommitted changes (the deployed code will not match any commit)"
git status -sb 2>/dev/null | head -1 | grep -q 'ahead' && warn "this branch has commits that are not pushed yet"
# PUBLISHED classes only: a class whose module says PUBLISHED = False is in the repo and tested, but the deployed API (MSI_INCLUDE_UNPUBLISHED unset) does not list it.
EXPECT_CLASSES="$("$PY" -c 'import engine; print(len(engine.published_classes()))' 2>/dev/null)" || EXPECT_CLASSES=""
[ -n "$EXPECT_CLASSES" ] && ok "this checkout publishes $EXPECT_CLASSES classes (the live API must report the same)" || warn "could not count the published classes of this checkout"

printf '\nPlan:  %s\n' "project=$PROJECT_ID region=$REGION service=$SERVICE site=$SITE_URL"
printf '       tests=%s  api=%s  web=%s  firestore-rules=%s\n' "$WANT_TESTS" "$WANT_API" "$WANT_WEB" "$((WANT_WEB * (1 - NO_RULES)))"
if [ "$ASSUME_YES" != 1 ] && [ "$DRY_RUN" != 1 ]; then
  printf 'Deploy now? [y/N] '; read -r ANSWER
  case "$ANSWER" in y|Y|yes|YES) ;; *) echo "aborted, nothing deployed."; exit 0 ;; esac
fi

# --------------------------------------------------------------------------------------------------------------------------- 2. tests
if [ "$WANT_TESTS" = 1 ]; then
  step "Local regression run (tests/run_all.py --build): golden + API + web tests and the production build"
  "$PY" tests/run_all.py --build; RC=$?
  HINT="run: $PY tests/run_all.py  (add --class <id> for one class) and fix what it reports, or use --skip-tests if you know why it is red"
  [ "$RC" = 0 ] || fail "the regression run failed (exit $RC)"
  ok "all green"
fi

API_URL="${API_URL:-}"
# --------------------------------------------------------------------------------------------------------------------------- 3. API
if [ "$WANT_API" = 1 ]; then
  step "Deploy the API to Cloud Run ($SERVICE in $REGION)"
  PROJECT_ID="$PROJECT_ID" REGION="$REGION" SERVICE="$SERVICE" CORS_ORIGINS="$CORS_ORIGINS" DRY_RUN="$DRY_RUN" \
    bash "$DEPLOY_DIR/deploy_api.sh" 2>&1 | tee "$TMP/api.log"; RC=${PIPESTATUS[0]}
  HINT="read the gcloud / Cloud Build output above (Cloud Build logs: https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID)"
  [ "$RC" = 0 ] || fail "deploy_api.sh failed (exit $RC)"
  if [ "$DRY_RUN" = 1 ]; then
    ok "dry run: the build context was staged and the gcloud command printed"
    API_URL="${API_URL:-https://dry-run.invalid}"
  else
    API_URL="$(grep '^API_URL=' "$TMP/api.log" | tail -1 | cut -d= -f2-)"
    [ -n "$API_URL" ] || fail "the deploy finished but printed no API_URL"
    ok "deployed: $API_URL"
    REV="$(gcloud --project "$PROJECT_ID" run services describe "$SERVICE" --region "$REGION" --format=json 2>/dev/null | "$PY" -c '
import json, sys
d = json.load(sys.stdin); s = d["status"]
ready = [c for c in s.get("conditions", []) if c.get("type") == "Ready"]
traffic = {t.get("revisionName") or "latest": t.get("percent", 0) for t in s.get("traffic", [])}
good = bool(ready) and ready[0].get("status") == "True" and s.get("latestCreatedRevisionName") == s.get("latestReadyRevisionName") and sum(traffic.values()) == 100
print(("OK " if good else "BAD ") + str(s.get("latestReadyRevisionName")) + " traffic=" + json.dumps(traffic))')"
    case "$REV" in OK*) ok "Cloud Run revision ready and serving 100%: ${REV#OK }" ;; *) HINT="open the Cloud Run console for $SERVICE"; fail "the new revision is not ready / not receiving all traffic: $REV" ;; esac
  fi

  step "Smoke-test the live API (every class: defaults -> compute -> stat values; error paths; CORS for $SITE_URL)"
  if [ "$DRY_RUN" = 1 ]; then ok "dry run: skipped"; else
    API_URL="$API_URL" SMOKE_ORIGIN="$SITE_URL" EXPECT_CLASSES="$EXPECT_CLASSES" bash "$DEPLOY_DIR/smoke_test.sh" 2>&1 | tee "$TMP/smoke.log"; RC=${PIPESTATUS[0]}
    HINT="the lines starting with FAIL above say which check broke; the API revision is already live, the previous web page keeps working until the web step runs"
    [ "$RC" = 0 ] || fail "the API smoke test failed (exit $RC)"
    ok "API smoke test passed"
  fi
fi

# --------------------------------------------------------------------------------------------------------------------------- 4. web
if [ "$WANT_WEB" = 1 ]; then
  if [ -z "$API_URL" ] && [ "$DRY_RUN" != 1 ]; then
    API_URL="$(gcloud --project "$PROJECT_ID" run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)' 2>/dev/null)"
  fi
  step "Build the web page against ${API_URL:-the API} and deploy it to Firebase Hosting$([ "$NO_RULES" = 1 ] || echo ' + the Firestore rules')"
  [ -n "$API_URL" ] || { HINT="deploy the API first, or set API_URL=https://..."; fail "no API URL known"; }
  RULES=$((1 - NO_RULES))
  API_URL="$API_URL" STATIC_HOST=firebase FIREBASE_PROJECT="$FIREBASE_PROJECT" FIREBASE_DEPLOY_RULES="$RULES" DRY_RUN="$DRY_RUN" \
    bash "$DEPLOY_DIR/deploy_web.sh" 2>&1 | tee "$TMP/web.log"; RC=${PIPESTATUS[0]}
  HINT="read the build / firebase output above; Firebase errors about login: cd deploy/firebase && npx firebase-tools login"
  [ "$RC" = 0 ] || fail "deploy_web.sh failed (exit $RC)"
  if [ "$DRY_RUN" = 1 ]; then ok "dry run: nothing published"; else
    grep -q 'Deploy complete' "$TMP/web.log" || fail "Firebase did not report 'Deploy complete'"
    ok "Firebase reported 'Deploy complete'"
    if grep -q '^VITE_FIREBASE_PROJECT_ID=' web/.env.production 2>/dev/null; then
      grep -q 'accounts' "$TMP/web.log" && grep -qE 'accounts: (ENABLED|VITE_FIREBASE)' "$TMP/web.log" && ok "accounts feature is built in" || warn "the build log does not confirm the accounts feature"
    fi
    [ "$RULES" = 1 ] && { grep -qiE 'rules.*(released|uploaded)|released rules' "$TMP/web.log" && ok "Firestore rules released" || warn "could not confirm the Firestore rules release in the log (check the Firebase console)"; }
  fi
fi

# --------------------------------------------------------------------------------------------------------------------------- 5. live checks
step "Verify the live site and API"
if [ "$DRY_RUN" = 1 ]; then ok "dry run: skipped"; else
  if [ "$WANT_WEB" = 1 ]; then
    LOCAL_JS="$(grep -o 'assets/index-[^"]*\.js' web/dist/index.html | head -1)"
    GOT=""
    for i in 1 2 3 4 5 6; do                                   # the CDN can take a few seconds to serve the new files
      curl -fsS --max-time 30 -H 'Cache-Control: no-cache' "$SITE_URL/?cb=$(date +%s)" -o "$TMP/index.html" 2>/dev/null \
        && grep -q "$LOCAL_JS" "$TMP/index.html" && { GOT=1; break; }
      sleep 10
    done
    HINT="open $SITE_URL with a hard refresh; if it still serves the old page, wait a minute and run: curl -s $SITE_URL | grep assets/index"
    [ -n "$GOT" ] || fail "the live page does not serve the build we just deployed ($LOCAL_JS)"
    ok "$SITE_URL serves the new build ($LOCAL_JS)"
    curl -fsS --max-time 30 "$SITE_URL/$LOCAL_JS" -o "$TMP/bundle.js" || fail "could not download the live bundle"
    grep -qF "$API_URL" "$TMP/bundle.js" || fail "the live bundle does not contain the API URL $API_URL"
    ok "live bundle points at $API_URL"
    if grep -q '^VITE_FIREBASE_PROJECT_ID=' web/.env.production 2>/dev/null; then
      FB_ID="$(grep '^VITE_FIREBASE_PROJECT_ID=' web/.env.production | cut -d= -f2-)"
      CHUNKS="$(grep -rlF "$FB_ID" web/dist/assets 2>/dev/null | head -1)"
      [ -n "$CHUNKS" ] && ok "accounts config is inside the built files" || warn "the Firebase project id was not found in the built files"
    fi
  fi
  if [ -n "$API_URL" ] && [ "$API_URL" != "https://dry-run.invalid" ]; then
    curl -fsS --max-time 60 --retry 2 "$API_URL/api/classes" -o "$TMP/classes.json" || fail "GET $API_URL/api/classes failed"
    LIVE="$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); d=d.get("classes",d) if isinstance(d,dict) else d; print(len(d))' "$TMP/classes.json")"
    [ -z "$EXPECT_CLASSES" ] || [ "$LIVE" = "$EXPECT_CLASSES" ] || fail "the live API lists $LIVE classes but this checkout has $EXPECT_CLASSES"
    ok "the live API lists $LIVE classes"
    ORIGIN_OK="$(curl -sS --max-time 30 -I -H "Origin: $SITE_URL" "$API_URL/api/classes" 2>/dev/null | tr -d '\r' | grep -i '^access-control-allow-origin:' | head -1)"
    case "$ORIGIN_OK" in *"$SITE_URL"*|*'*'*) ok "CORS allows $SITE_URL" ;; *) HINT="re-run with the right CORS_ORIGINS"; fail "the API does not allow the origin $SITE_URL (got: ${ORIGIN_OK:-no CORS header})" ;; esac
  fi
fi

printf '\n==> ALL DONE in %ds.  Site: %s   API: %s\n' "$SECONDS" "$SITE_URL" "${API_URL:-n/a}"
[ "$DRY_RUN" = 1 ] || printf '    Open the site with a hard refresh (Cmd+Shift+R) and try a class.\n'
exit 0
