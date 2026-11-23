#!/usr/bin/env bash
# Black-box smoke test of a deployed (or local) API.  Exit code 0 = every check passed, 1 = at least one failed.
#
#   deploy/smoke_test.sh https://msi-api-xxxx-uc.a.run.app
#   API_URL=http://localhost:8000 SMOKE_ORIGIN=http://localhost:5173 deploy/smoke_test.sh
#
# Needs: bash, curl, python3 (only to read JSON).  Makes ~35 requests (well under the default 120/min rate limit; a 429 is reported as a failure).
# Checks: /api/health; /api/classes (count = EXPECT_CLASSES, default 12); per class: GET defaults -> POST compute with that body (200, finite
# total_dps > 0) and, for classes whose status says stat_values, POST sensitivity; POST compute with the minimal body {}; the error paths
# (422 unknown key, 404 unknown class); and, if SMOKE_ORIGIN is set, the CORS preflight for that origin (allowed) and for a foreign origin (refused).
set -uo pipefail
# shellcheck source=deploy/_common.sh
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
load_env_file

API_URL="${1:-${API_URL:-}}"
[ -n "$API_URL" ] || die "usage: smoke_test.sh <api-url>   (or set API_URL)"
API_URL="${API_URL%/}"
EXPECT_CLASSES="${EXPECT_CLASSES:-12}"
require_cmd curl; require_cmd python3

TMP="$(mktemp -d "${TMPDIR:-/tmp}/msi-smoke.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAILS=0
CODE=""; BODY="$TMP/body"; HDRS="$TMP/headers"

pass() { printf '  ok    %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }

# call METHOD PATH [json-body] [extra curl args...]  ->  sets CODE; body in $BODY, response headers in $HDRS.
# --retry covers the Cloud Run cold start (first request can take several seconds) and transient 5xx from the platform.
call() {
  local method="$1" path="$2" data="${3:-}"; shift 2; [ $# -gt 0 ] && shift
  local args=(-sS --max-time 60 --retry 3 --retry-delay 2 --retry-connrefused -o "$BODY" -D "$HDRS" -w '%{http_code}' -X "$method")
  if [ -n "$data" ]; then args+=(-H 'Content-Type: application/json' --data-binary "$data"); fi
  CODE="$(curl "${args[@]}" "$@" "$API_URL$path" 2>"$TMP/curl_err")" || { CODE="000"; : > "$BODY"; }
}

# jget FILE 'python expression on d' -> prints the value (empty on any error)
jget() { python3 -c 'import json,sys
try:
    d = json.load(open(sys.argv[1])); v = eval(sys.argv[2], {"d": d}); print("" if v is None else v)
except Exception:
    pass' "$1" "$2"; }

expect() {   # expect "label" expected_code   (uses the last call)
  if [ "$CODE" = "$2" ]; then pass "$1 -> $CODE"; return 0; fi
  fail "$1 -> HTTP $CODE (expected $2): $(head -c 200 "$BODY" | tr '\n' ' ') $(head -c 200 "$TMP/curl_err" 2>/dev/null)"; return 1
}

check_dps() {   # check_dps "label"  : the last response has a finite total_dps > 0
  local v; v="$(jget "$BODY" 'd["total_dps"] if isinstance(d["total_dps"], (int, float)) and d["total_dps"] > 0 and d["total_dps"] < 1e300 else ""')"
  if [ -n "$v" ]; then pass "$1 total_dps=$v"; else fail "$1: total_dps missing / not a positive finite number"; fi
}

echo "API: $API_URL"

echo "health"
call GET /api/health
if expect "GET /api/health" 200; then
  [ "$(jget "$BODY" 'd["status"]')" = "ok" ] && pass "status ok, version $(jget "$BODY" 'd.get("version")')" || fail "health body has no status=ok"
fi

echo "classes"
call GET /api/classes
if expect "GET /api/classes" 200; then
  N="$(jget "$BODY" 'len(d["classes"])')"
  [ "$N" = "$EXPECT_CLASSES" ] && pass "$N classes" || fail "got $N classes, expected $EXPECT_CLASSES (set EXPECT_CLASSES if that is intended)"
  # one line per class: id <tab> has-stat-values (1/0)
  python3 -c 'import json,sys
for c in json.load(open(sys.argv[1]))["classes"]:
    print(c["id"], 1 if (c.get("status") or {}).get("stat_values") else 0)' "$BODY" > "$TMP/classes.txt" 2>/dev/null || : > "$TMP/classes.txt"
fi
[ -s "$TMP/classes.txt" ] || { fail "could not read the class list; stopping"; echo "FAILED ($FAILS)"; exit 1; }

echo "per class"
while read -r CID SENS; do
  call GET "/api/classes/$CID/defaults"
  if expect "$CID defaults" 200; then
    cp "$BODY" "$TMP/defaults.json"
    call POST "/api/classes/$CID/compute" "$(cat "$TMP/defaults.json")"
    if expect "$CID compute (defaults body)" 200; then check_dps "$CID compute"; fi
  fi
  if [ "$SENS" = "1" ]; then
    call POST "/api/classes/$CID/sensitivity" '{}'
    if expect "$CID sensitivity" 200; then
      [ -n "$(jget "$BODY" 'd["baseline_total"] if d["baseline_total"] > 0 else ""')" ] && pass "$CID sensitivity baseline_total > 0" || fail "$CID sensitivity: no positive baseline_total"
    fi
  fi
done < "$TMP/classes.txt"

FIRST="$(head -n1 "$TMP/classes.txt" | cut -d' ' -f1)"
echo "minimal body / error paths"
call POST "/api/classes/$FIRST/compute" '{}'
if expect "$FIRST compute with {}" 200; then check_dps "$FIRST compute {}"; fi
call POST "/api/classes/$FIRST/compute" '{"definitely_not_a_field": 1}'
expect "$FIRST compute with an unknown key is rejected" 422
call GET /api/classes/no_such_class/schema
expect "unknown class" 404

if [ -n "${SMOKE_ORIGIN:-}" ]; then
  echo "CORS (origin $SMOKE_ORIGIN)"
  call OPTIONS "/api/classes/$FIRST/compute" "" -H "Origin: $SMOKE_ORIGIN" -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'
  if [ "$CODE" = "200" ] || [ "$CODE" = "204" ]; then
    grep -qi "^access-control-allow-origin: $SMOKE_ORIGIN\r\?$" "$HDRS" && pass "preflight allows $SMOKE_ORIGIN" || fail "preflight answered $CODE but without Access-Control-Allow-Origin: $SMOKE_ORIGIN (check CORS_ORIGINS)"
  else
    fail "preflight for $SMOKE_ORIGIN -> HTTP $CODE (check CORS_ORIGINS)"
  fi
  call OPTIONS "/api/classes/$FIRST/compute" "" -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'
  if grep -qi '^access-control-allow-origin:' "$HDRS"; then
    grep -qi '^access-control-allow-origin: \*' "$HDRS" && fail "any origin is allowed (CORS_ORIGINS contains '*')" || fail "a foreign origin is allowed"
  else
    pass "preflight from a foreign origin is refused"
  fi
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "ALL CHECKS PASSED"; exit 0; fi
echo "FAILED: $FAILS check(s)"; exit 1
