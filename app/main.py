import asyncio
import json
import time
import traceback

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import alerts, audit, config, db, history, registry
from app.checker import check_endpoint, Endpoint

app = FastAPI(title="Sentinel")

_ws_clients: set[WebSocket] = set()


def _log_audit(
    actor: str,
    endpoint: str,
    action: str,
    status_code: int | None = None,
    latency_ms: float | None = None,
    detail: str | None = None,
) -> None:
    if config.DATABASE_URL:
        db.log_access(actor, endpoint, action, status_code, latency_ms, detail)
    else:
        audit.log(actor, endpoint, action, status_code, latency_ms, detail)


class EndpointIn(BaseModel):
    name: str
    url: str
    method: str = "GET"
    actor: str = "unknown"


@app.post("/endpoints")
def create_endpoint(payload: EndpointIn):
    record = registry.register(payload.name, payload.url, payload.method)
    _log_audit(payload.actor, payload.name, "register")
    return record


@app.get("/endpoints")
def get_endpoints():
    return registry.list_all()


@app.post("/endpoints/{endpoint_id}/approve")
def approve_endpoint(endpoint_id: int, actor: str = "unknown"):
    record = registry.set_status(endpoint_id, "approved")
    if record is None:
        raise HTTPException(status_code=404, detail="endpoint not found")
    _log_audit(actor, record["name"], "approve")
    return record


@app.post("/endpoints/{endpoint_id}/deprecate")
def deprecate_endpoint(endpoint_id: int, actor: str = "unknown"):
    record = registry.set_status(endpoint_id, "deprecated")
    if record is None:
        raise HTTPException(status_code=404, detail="endpoint not found")
    _log_audit(actor, record["name"], "deprecate")
    return record


@app.get("/access-log")
def get_access_log(limit: int = 100):
    if config.DATABASE_URL:
        return db.list_access_log(limit)
    return audit.list_recent(limit)


@app.get("/history")
def get_history(limit: int = 200):
    """Recently recorded checks, oldest first, with each endpoint's current baseline attached —
    lets the dashboard rehydrate the Live Status table and latency charts on page load instead of
    starting empty, since that data already lives in the persisted history file either way."""
    rows = list(reversed(history.recent_checks(limit)))
    baseline_cache: dict[str, tuple[float, float] | None] = {}
    enriched = []
    for row in rows:
        endpoint = row["endpoint"]
        if endpoint not in baseline_cache:
            baseline_cache[endpoint] = history.overall_stats(endpoint, config.DRIFT_MIN_SAMPLES)
        stats = baseline_cache[endpoint]
        enriched.append(
            {
                "endpoint": endpoint,
                "status_code": row["status_code"],
                "latency_ms": row["latency_ms"],
                "baseline_ms": stats[0] if stats else None,
                "baseline_stdev_ms": stats[1] if stats else None,
                "attempts": row["attempts"] or 1,
                "ok": bool(row["ok"]),
                "timestamp": row["created_at"],
                "alerts": [],
            }
        )
    return enriched


_dummy_slow = False


@app.get("/dummy/health")
async def dummy_health():
    """Self-hosted controllable target for demoing/testing anomaly detection end-to-end."""
    await asyncio.sleep(0.6 if _dummy_slow else 0.02)
    return {"status": "ok", "slow": _dummy_slow}


@app.post("/dummy/toggle")
def dummy_toggle():
    global _dummy_slow
    _dummy_slow = not _dummy_slow
    return {"slow": _dummy_slow}


_DRIFT_BASE_MS = 30
_DRIFT_RAMP_MS_PER_SEC = 15
_DRIFT_MAX_MS = 1500
_dummy_drift_started_at: float | None = None


@app.get("/dummy/drift")
async def dummy_drift():
    """Self-hosted target that climbs gradually once started, instead of spiking — a different anomaly shape than /dummy/health."""
    delay_ms = _DRIFT_BASE_MS
    if _dummy_drift_started_at is not None:
        elapsed = time.monotonic() - _dummy_drift_started_at
        delay_ms = min(_DRIFT_MAX_MS, _DRIFT_BASE_MS + elapsed * _DRIFT_RAMP_MS_PER_SEC)
    await asyncio.sleep(delay_ms / 1000)
    return {"status": "ok", "climbing": _dummy_drift_started_at is not None, "delay_ms": round(delay_ms)}


@app.post("/dummy/drift/start")
def dummy_drift_start():
    global _dummy_drift_started_at
    _dummy_drift_started_at = time.monotonic()
    return {"climbing": True}


@app.post("/dummy/drift/reset")
def dummy_drift_reset():
    global _dummy_drift_started_at
    _dummy_drift_started_at = None
    return {"climbing": False}


@app.get("/")
def dashboard():
    return FileResponse("app/static/index.html")


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)


async def _broadcast(payload: dict) -> None:
    message = json.dumps(payload)
    dead = []
    for client in _ws_clients:
        try:
            await client.send_text(message)
        except Exception:
            dead.append(client)
    for client in dead:
        _ws_clients.discard(client)


async def _process_result(result) -> None:
    alert = alerts.evaluate(result)
    if alert:
        alerts.log_alert(alert)
    drift_alert, baseline_ms, stdev_ms = alerts.check_drift(result)
    if drift_alert:
        alerts.log_alert(drift_alert)
    trend_alert = alerts.check_trend(result)
    if trend_alert:
        alerts.log_alert(trend_alert)

    fired = [a for a in (alert, drift_alert, trend_alert) if a is not None]
    await _broadcast(
        {
            "endpoint": result.endpoint_name,
            "url": result.url,
            "status_code": result.status_code,
            "latency_ms": result.latency_ms,
            "baseline_ms": baseline_ms,
            "baseline_stdev_ms": stdev_ms,
            "attempts": result.attempts,
            "ok": result.ok,
            "timestamp": result.timestamp.isoformat(),
            "alerts": [{"severity": a.severity, "message": a.message} for a in fired],
        }
    )
    _log_audit("checker", result.endpoint_name, "check", result.status_code, result.latency_ms)
    for fired_alert in fired:
        _log_audit(
            "checker",
            result.endpoint_name,
            "alert",
            result.status_code,
            result.latency_ms,
            f"[{fired_alert.severity}] {fired_alert.message}",
        )


async def _monitor_loop() -> None:
    """Runs for the lifetime of the app. Must never die — any exception here silently
    stops all monitoring with no visible sign in the UI, so every step below is guarded."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                targets = [
                    Endpoint(name=e["name"], url=e["url"], method=e["method"])
                    for e in registry.approved()
                ]
                if targets:
                    results = await asyncio.gather(
                        *(check_endpoint(client, ep) for ep in targets), return_exceptions=True
                    )
                    for result in results:
                        if isinstance(result, BaseException):
                            traceback.print_exc()
                            continue
                        try:
                            await _process_result(result)
                        except Exception:
                            traceback.print_exc()
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


@app.on_event("startup")
async def on_startup():
    if config.DATABASE_URL:
        db.init_schema()
    was_empty = not registry.list_all()
    registry.seed_defaults()
    if was_empty:
        for entry in registry.list_all():
            _log_audit("system", entry["name"], "seed")
    asyncio.create_task(_monitor_loop())
