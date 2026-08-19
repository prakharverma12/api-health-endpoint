import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app import alerts, config


class RateLimited(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"rate-limited with HTTP {status_code}")
        self.status_code = status_code


@dataclass
class Endpoint:
    name: str
    url: str
    method: str = "GET"

@dataclass
class CheckResult:
    endpoint_name: str
    url: str
    status_code: Optional[int]
    latency_ms: float
    attempts: int
    error: Optional[str]
    timestamp: datetime = field(default_factory=alerts.now)

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 400


async def _request(client: httpx.AsyncClient, endpoint: Endpoint) -> httpx.Response:
    response = await client.request(
        endpoint.method, endpoint.url, timeout=config.REQUEST_TIMEOUT_SECONDS
    )
    if response.status_code in (429, 503):
        raise RateLimited(response.status_code)
    return response


async def check_endpoint(client: httpx.AsyncClient, endpoint: Endpoint) -> CheckResult:
    start = time.perf_counter()
    attempts = 0
    status_code: Optional[int] = None
    error: Optional[str] = None

    retrying = AsyncRetrying(
        retry=retry_if_exception_type(RateLimited),
        wait=wait_exponential(multiplier=config.BACKOFF_BASE_SECONDS, min=config.BACKOFF_BASE_SECONDS, max=30),
        stop=stop_after_attempt(config.MAX_RETRIES),
        reraise=True,
    )
    try:
        async for attempt in retrying:
            with attempt:
                attempts += 1
                response = await _request(client, endpoint)
        status_code = response.status_code
    except RateLimited as exc:
        attempts = retrying.statistics.get("attempt_number", attempts)
        status_code = exc.status_code
    except httpx.HTTPError as exc:
        attempts = attempts or 1
        error = str(exc)

    latency_ms = (time.perf_counter() - start) * 1000
    return CheckResult(
        endpoint_name=endpoint.name,
        url=endpoint.url,
        status_code=status_code,
        latency_ms=latency_ms,
        attempts=attempts,
        error=error,
    )


def print_result(result: CheckResult) -> None:
    ts = result.timestamp.strftime("%H:%M:%S")
    state = "OK" if result.ok else "FAIL"
    print(
        f"[{ts}] {state:4} {result.endpoint_name:20} "
        f"status={result.status_code} latency={result.latency_ms:.0f}ms attempts={result.attempts}"
    )


async def run_checker(
    endpoints: list[Endpoint],
    on_result: Callable[[CheckResult], Awaitable[None] | None] = print_result,
    iterations: Optional[int] = None,
) -> None:
    """Poll every registered endpoint on a fixed interval, forever unless `iterations` is set."""
    count = 0
    async with httpx.AsyncClient() as client:
        while iterations is None or count < iterations:
            results = await asyncio.gather(*(check_endpoint(client, ep) for ep in endpoints))
            for result in results:
                maybe_coro = on_result(result)
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
                alert = alerts.evaluate(result)
                if alert:
                    alerts.log_alert(alert)
                drift_alert, _, _ = alerts.check_drift(result)
                if drift_alert:
                    alerts.log_alert(drift_alert)
                trend_alert = alerts.check_trend(result)
                if trend_alert:
                    alerts.log_alert(trend_alert)
            count += 1
            if iterations is None or count < iterations:
                await asyncio.sleep(config.POLL_INTERVAL_SECONDS)


DEMO_ENDPOINTS = [
    Endpoint(name="example-ok", url="https://example.com"),
    Endpoint(name="postman-ok", url="https://postman-echo.com/status/200"),
    Endpoint(name="postman-rate-limited", url="https://postman-echo.com/status/429"),
    Endpoint(name="postman-server-error", url="https://postman-echo.com/status/503"),
]


if __name__ == "__main__":
    asyncio.run(run_checker(DEMO_ENDPOINTS))
