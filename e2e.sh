#!/usr/bin/env bash
# End-to-end check: backend against the live herdr, frontend via the vite proxy.
#
# Ports are picked dynamically because this machine may already have services
# bound on the usual dev ports.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/backend/.venv/bin/python"

free_port() {
  "$PY" - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

BACK_PORT="${BACK_PORT:-$(free_port)}"
FRONT_PORT="${FRONT_PORT:-$(free_port)}"

cleanup() {
  kill "${BACK_PID:-0}" 2>/dev/null || true
  kill "${FRONT_PID:-0}" 2>/dev/null || true
}
trap cleanup EXIT

echo "== backend  :$BACK_PORT =="
(cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACK_PORT" > /tmp/e2e-back.log 2>&1) &
BACK_PID=$!

for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$BACK_PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.25
done

echo "== frontend :$FRONT_PORT =="
(cd "$ROOT/example/frontend" && HERDR_RESTFUL_URL="http://127.0.0.1:$BACK_PORT" exec npx vite --host 127.0.0.1 --port "$FRONT_PORT" --strictPort > /tmp/e2e-front.log 2>&1) &
FRONT_PID=$!

for _ in $(seq 1 80); do
  curl -sf "http://127.0.0.1:$FRONT_PORT/" >/dev/null 2>&1 && break
  sleep 0.25
done

fail=0
say() { printf '%-46s %s\n' "$1" "$2"; }

code=$(curl -s -o /tmp/e2e.html -w '%{http_code}' "http://127.0.0.1:$FRONT_PORT/")
[ "$code" = "200" ] && say "frontend serves index.html" "PASS ($code)" || { say "frontend serves index.html" "FAIL ($code)"; fail=1; }
grep -q 'id="root"' /tmp/e2e.html && say "frontend has #root mount" "PASS" || { say "frontend has #root mount" "FAIL"; fail=1; }
grep -q 'herdr dashboard' /tmp/e2e.html && say "frontend title is the dashboard" "PASS" || { say "frontend title is the dashboard" "FAIL"; fail=1; }

code=$(curl -s -o /tmp/e2e.snap -w '%{http_code}' "http://127.0.0.1:$FRONT_PORT/api/v1/session/snapshot")
[ "$code" = "200" ] && say "vite proxy -> /api/v1/session/snapshot" "PASS ($code)" || { say "vite proxy snapshot" "FAIL ($code)"; fail=1; }

"$PY" - <<'PY'
import json
d = json.load(open('/tmp/e2e.snap'))
s = d['snapshot']
print(f"{'snapshot ws/tabs/panes/agents':<46} {len(s['workspaces'])}/{len(s['tabs'])}/{len(s['panes'])}/{len(s.get('agents', []))}")
PY

for path in /api/v1/workspaces /api/v1/tabs /api/v1/panes /api/v1/agents /api/v1/server; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$FRONT_PORT$path")
  [ "$code" = "200" ] && say "vite proxy -> $path" "PASS ($code)" || { say "vite proxy -> $path" "FAIL ($code)"; fail=1; }
done

# read the focused pane's output through the proxy
echo "$BACK_PORT" > /tmp/e2e-port
PANE_ID=$("$PY" - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:%s/api/v1/panes/current" % open('/tmp/e2e-port').read().strip()))
print(d["pane"]["pane_id"])
PY
)
if [ -n "$PANE_ID" ]; then
  code=$(curl -s -o /tmp/e2e.out -w '%{http_code}' "http://127.0.0.1:$FRONT_PORT/api/v1/panes/$PANE_ID/output?source=recent&lines=10")
  [ "$code" = "200" ] && say "pane output for $PANE_ID" "PASS ($code)" || { say "pane output for $PANE_ID" "FAIL ($code)"; fail=1; }
else
  say "resolve focused pane id" "FAIL"
  fail=1
fi

# remember the focused workspace so we can restore it after the probe
echo "$BACK_PORT" > /tmp/e2e-port
ORIG_FOCUS=$("$PY" - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:%s/api/v1/workspaces" % open('/tmp/e2e-port').read().strip()))
print(next((w['workspace_id'] for w in d['workspaces'] if w.get('focused')), ''))
PY
)

# SSE through the proxy
curl -sN --max-time 5 "http://127.0.0.1:$FRONT_PORT/api/v1/events" > /tmp/e2e.sse 2>&1 &
SSE_PID=$!
sleep 1.2
curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/v1/notifications" -H 'content-type: application/json' -d '{"title":"e2e probe"}' >/dev/null
# focus a workspace that is not currently focused, so a focus event is emitted
FOCUS_ID=$("$PY" - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:%s/api/v1/workspaces" % open('/tmp/e2e-port').read().strip()))
ws = d['workspaces']
target = next((w['workspace_id'] for w in ws if not w.get('focused')), ws[0]['workspace_id'])
print(target)
PY
)
curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/v1/workspaces/$FOCUS_ID/focus" >/dev/null
wait $SSE_PID 2>/dev/null

# put focus back where it was
if [ -n "$ORIG_FOCUS" ]; then
  curl -s -X POST "http://127.0.0.1:$BACK_PORT/api/v1/workspaces/$ORIG_FOCUS/focus" >/dev/null
fi

if grep -q 'event: bridge.open' /tmp/e2e.sse; then
  say "SSE bridge.open through proxy" "PASS"
else
  say "SSE bridge.open through proxy" "FAIL"; fail=1
fi
if grep -qE 'event: (workspace_focused|tab_focused|pane_focused)' /tmp/e2e.sse; then
  say "SSE delivered live focus events" "PASS"
else
  say "SSE delivered live focus events" "FAIL"; fail=1
fi

echo
if [ "$fail" -eq 0 ]; then echo "E2E PASSED"; else echo "E2E FAILURES"; exit 1; fi
