#!/usr/bin/env bash
# Smoke test the REST API against a live herdr server.
set -u
BASE="${BASE:-http://127.0.0.1:8080}"
PORT="${PORT:-8080}"
PY="${PY:-.venv/bin/python}"

cleanup() { kill "${SERVER_PID:-0}" 2>/dev/null || true; }
trap cleanup EXIT

.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > /tmp/herdr-restful.log 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
  curl -sf "$BASE/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.25
done

fail=0
check() {
  local name="$1" path="$2" expect="${3:-200}" body="${4:-}"
  local args=(-s -o /tmp/smoke.out -w '%{http_code}' "$BASE$path")
  if [ -n "$body" ]; then
    args=(-s -o /tmp/smoke.out -w '%{http_code}' -X POST -H 'content-type: application/json' -d "$body" "$BASE$path")
  fi
  local code
  code=$(curl "${args[@]}")
  if [ "$code" = "$expect" ]; then
    echo "PASS  $name ($code)"
  else
    echo "FAIL  $name: expected $expect got $code"
    head -c 300 /tmp/smoke.out; echo
    fail=1
  fi
}

check "health"            "/api/v1/health"
check "server info"       "/api/v1/server"
check "session snapshot"  "/api/v1/session/snapshot"
check "workspace list"    "/api/v1/workspaces"
check "tab list"          "/api/v1/tabs"
check "pane list"         "/api/v1/panes"
check "agent list"        "/api/v1/agents"
check "pane current"      "/api/v1/panes/current"
check "layout export"     "/api/v1/layout/export"
check "agent manifests"   "/api/v1/server/agent-manifests"
check "integrations"      "/api/v1/integrations"
check "404 unknown ws"    "/api/v1/workspaces/w-does-not-exist" 404

# worktree listing needs a workspace inside a git work tree
code=$(curl -s -o /tmp/smoke.out -w '%{http_code}' "$BASE/api/v1/worktrees")
if [ "$code" = "200" ] || [ "$code" = "409" ]; then
  echo "PASS  worktree list ($code)"
else
  echo "FAIL  worktree list: got $code"; head -c 300 /tmp/smoke.out; echo; fail=1
fi

# read output of the focused pane
PANE_ID=$("$PY" - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:8080/api/v1/panes/current"))
print(d["pane"]["pane_id"])
PY
)
check "pane get"          "/api/v1/panes/$PANE_ID"
check "pane output"       "/api/v1/panes/$PANE_ID/output?source=recent&lines=20"
check "pane process-info" "/api/v1/panes/$PANE_ID/process-info"
check "pane layout"       "/api/v1/panes/$PANE_ID/layout"

echo
echo "focused pane: $PANE_ID"
if [ "$fail" -eq 0 ]; then echo "ALL SMOKE CHECKS PASSED"; else echo "SMOKE FAILURES PRESENT"; exit 1; fi
