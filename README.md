# Sentinel MVP

API health-check, alerting, and governance prototype — see `PS1_Deep_Dive_Analysis_Sentinel.pptx` for the pitch this supports.

## Setup

```
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env
```

## Run

**Phase 1 — standalone checker (console only, no server):**
```
./venv/Scripts/python.exe -m app.checker
```

**Phase 2/3 — dashboard + governance API:**
```
./venv/Scripts/python.exe -m uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 for the live dashboard. Register an endpoint, approve it, and watch live status arrive over the WebSocket.

Set `DATABASE_URL` in `.env` to a Postgres connection string to enable the audit trail — the app creates its tables on startup and every check + governance action (register/approve/deprecate) is written to `access_log`. Without `DATABASE_URL`, the dashboard runs fully functional but unlogged (`GET /access-log` returns 503).
