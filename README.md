# herdr-restful

RESTful API wrapper around the [herdr](https://herdr.dev) local socket API, plus an
example dashboard used for validation.

herdr exposes a newline-delimited JSON protocol on a local Unix socket
(`~/.config/herdr/herdr.sock`). This project turns that protocol into a
resource-oriented HTTP API and streams herdr events to browsers over SSE.

```
herdr-restful/
├── backend/             # the deliverable: FastAPI service
├── example/
│   └── frontend/        # validation dashboard (not a shipped product)
├── e2e.sh               # end-to-end check against a live herdr
└── README.md
```

## Requirements

- herdr >= 0.9.0 with a running server (`herdr status`)
- Python 3.11+
- Node 18+ (only for `example/frontend`)

## Backend

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Interactive OpenAPI docs: <http://127.0.0.1:8080/docs>

### Socket path resolution

Matches the herdr documentation, lowest precedence first:

1. `HERDR_RESTFUL_SOCKET_PATH` / `HERDR_SOCKET_PATH` — explicit override
2. `HERDR_RESTFUL_SESSION` / `HERDR_SESSION` — `~/.config/herdr/sessions/<name>/herdr.sock`
3. `~/.config/herdr/herdr.sock`

### Response convention

Successful responses return the herdr `result` object verbatim, for example:

```json
{ "type": "pane_info", "pane": { "pane_id": "w1:p1", "agent_status": "working", ... } }
```

Errors use an HTTP status derived from the herdr error code plus:

```json
{ "detail": { "error": { "code": "pane_not_found", "message": "pane not found" } } }
```

| herdr code pattern | HTTP |
| --- | --- |
| `*_not_found`, `not_found` | 404 |
| `invalid_params`, `invalid_*` | 422 |
| `invalid_request` | 400 |
| `*_blocked`, `*_conflict`, `*_required`, `*_not_open`, `same_tab`, `not_git_*` | 409 |
| `*_unsupported` | 400 |
| `feature_disabled` | 501 |
| `*_timeout` | 504 |
| `rate_limited` | 429 |
| socket unreachable / request timeout | 503 |
| anything else | 502 |

## API surface

About 55 of herdr's 102 methods are exposed. Plugin management, pane graphics
and a few client-only methods are intentionally out of scope for this wrapper.

| Area | Endpoints |
| --- | --- |
| Server | `GET /api/v1/server`, `GET /api/v1/health`, `POST /api/v1/server/stop`, `POST /api/v1/server/reload-config`, `GET|POST /api/v1/server/agent-manifests[/reload]` |
| Session | `GET /api/v1/session/snapshot` |
| Workspaces | `GET|POST /api/v1/workspaces`, `GET|PATCH|DELETE /api/v1/workspaces/{id}`, `POST .../focus`, `POST .../move`, `POST /api/v1/workspaces/reorder`, `PUT .../metadata` |
| Worktrees | `GET|POST /api/v1/worktrees`, `POST /api/v1/worktrees/open`, `DELETE /api/v1/worktrees/{workspace_id}` |
| Tabs | `GET|POST /api/v1/tabs`, `GET|PATCH|DELETE /api/v1/tabs/{id}`, `POST .../focus`, `POST .../move` |
| Panes | `GET|POST /api/v1/panes`, `GET /api/v1/panes/current`, `GET|PATCH|DELETE /api/v1/panes/{id}`, `POST .../focus\|swap\|move\|zoom\|resize\|scroll\|wait-output`, `POST /api/v1/panes/split`, `POST /api/v1/panes/focus-direction`, `GET .../layout\|neighbor\|edges\|process-info\|output`, `POST .../input[/text|/keys]`, `PUT .../agent-status`, `PUT .../metadata` |
| Agents | `GET /api/v1/agents`, `GET|PATCH /api/v1/agents/{pane_id}`, `GET .../output\|explain`, `POST .../keys\|prompt\|wait\|focus`, `POST /api/v1/agents/start`, `PUT\|DELETE /api/v1/agents/view` |
| Layout | `GET /api/v1/layout/export`, `POST /api/v1/layout/apply`, `PATCH /api/v1/layout/split-ratio` |
| Events | `GET /api/v1/events` (SSE), `POST /api/v1/events/wait` |
| Notifications | `POST /api/v1/notifications` |
| Integrations | `GET|POST /api/v1/integrations`, `DELETE /api/v1/integrations/{target}` |

### SSE event stream

`GET /api/v1/events` bridges herdr's `events.subscribe` connection to
Server-Sent Events.

```bash
curl -N 'http://127.0.0.1:8080/api/v1/events'
curl -N 'http://127.0.0.1:8080/api/v1/events?types=workspace.focused,pane.updated'
curl -N 'http://127.0.0.1:8080/api/v1/events?types=pane.agent_status_changed&pane_id=w1:p1'
```

Notes:

- The first frame is `event: bridge.open`, sent only after herdr acknowledged
  the subscription, so clients cannot miss early events.
- Subscriptions use **dotted** names (`workspace.created`), matching the herdr
  request schema. Pushed frames use **underscore** kinds (`workspace_created`),
  matching the herdr event schema. Both are preserved as-is.
- Pane-scoped subscriptions (`pane.agent_status_changed`, `pane.scroll_changed`,
  `pane.output_matched`) require `pane_id` upstream; omitting it returns 400.
- With no `types` parameter the default is the full set of subscriptions that
  need no extra fields — what a dashboard wants.
- A `: keepalive` comment is emitted every `HERDR_RESTFUL_SSE_HEARTBEAT`
  seconds (default 15).

## Example dashboard

`example/frontend` is a validation client, not a shipped product. It renders
workspaces, tabs, panes and agents and stays live over SSE.

```bash
cd example/frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to :8080
```

Set `HERDR_RESTFUL_URL` if the backend is not on `http://127.0.0.1:8080`.

## Tests

```bash
# backend: 52 tests against an in-process fake herdr socket server
cd backend && .venv/bin/python -m pytest -q

# frontend: 19 tests (snapshot + event reducer, and a jsdom render of the dashboard)
cd example/frontend && npm test

# end-to-end against the live herdr (starts both servers on free ports)
./e2e.sh
```

The backend test suite runs a fake herdr that reproduces the real transport
semantics verified against herdr 0.9.0:

- one request per connection for plain calls (herdr closes after responding)
- `events.subscribe` keeps the connection open and pushes events
- errors are `{"id", "error": {"code", "message"}}`

SSE integration tests run the app under a real `uvicorn` server because
httpx's `ASGITransport` cannot drive an unbounded response stream.

## Protocol quirks worth knowing

Learned from the herdr 0.9.0 schema and live testing:

- Plain calls are **one request per connection** — herdr writes the response
  line and closes. The client opens a fresh connection per call rather than
  pooling.
- Subscription `type` values are dotted (`pane.updated`), but `events.wait`
  `match_event.event` values are underscored (`pane_updated`).
- Error codes are free-form strings; the documented `not_found` is in practice
  `workspace_not_found`, `pane_not_found`, `agent_not_found`, …
- `workspace.close` needs `close_group: true` for worktree-group parents,
  otherwise herdr answers `workspace_group_close_required`.
