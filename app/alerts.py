from dataclasses import dataclass
from datetime import datetime, timezone

from app import config, history


@dataclass
class Alert:
    endpoint_name: str
    severity: str  # "warning" | "critical"
    message: str
    timestamp: datetime


def evaluate(result) -> Alert | None:
    """Inspect a CheckResult and return an Alert if it warrants one."""
    if result.error:
        return Alert(
            endpoint_name=result.endpoint_name,
            severity="critical",
            message=f"{result.endpoint_name} unreachable: {result.error}",
            timestamp=result.timestamp,
        )

    if result.status_code in (429, 503):
        return Alert(
            endpoint_name=result.endpoint_name,
            severity="warning",
            message=(
                f"{result.endpoint_name} rate-limited (HTTP {result.status_code}) "
                f"after {result.attempts} attempt(s) with backoff"
            ),
            timestamp=result.timestamp,
        )

    if result.status_code >= 500:
        return Alert(
            endpoint_name=result.endpoint_name,
            severity="critical",
            message=f"{result.endpoint_name} returned HTTP {result.status_code}",
            timestamp=result.timestamp,
        )

    if result.status_code >= 400:
        return Alert(
            endpoint_name=result.endpoint_name,
            severity="warning",
            message=f"{result.endpoint_name} returned HTTP {result.status_code}",
            timestamp=result.timestamp,
        )

    return None


def check_drift(result) -> tuple[Alert | None, float | None, float | None]:
    """Compare against the holistic (all-time) latency baseline via z-score, then record this sample.

    A z-score (how many standard deviations above the mean) is used rather than a fixed
    ratio, since it self-adjusts to how noisy each endpoint naturally is — a jittery
    endpoint won't false-alarm on normal variance, a steady one will still catch a small
    but real deviation. The baseline itself is computed over the endpoint's entire history,
    not a sliding recent window, so it stays stable rather than shifting every check.

    Only meaningful for successful checks — a failure is already covered by evaluate().
    Returns (drift_alert, baseline_ms, stdev_ms) — baseline/stdev are returned even when
    no alert fires, so callers can display "mean ± stdev" and chart it.
    """
    drift_alert = None
    baseline_ms = None
    stdev_ms = None
    if result.ok:
        stats = history.overall_stats(result.endpoint_name, config.DRIFT_MIN_SAMPLES)
        if stats is not None:
            mean_ms, stdev_ms = stats
            baseline_ms = mean_ms
            if stdev_ms > 0:
                z_score = (result.latency_ms - mean_ms) / stdev_ms
                if z_score > config.DRIFT_ZSCORE_THRESHOLD:
                    drift_alert = Alert(
                        endpoint_name=result.endpoint_name,
                        severity="warning",
                        message=(
                            f"{result.endpoint_name} latency anomaly: {result.latency_ms:.0f}ms is "
                            f"{z_score:.1f} std-devs above the {mean_ms:.0f}ms all-time baseline "
                            f"(stdev={stdev_ms:.0f}ms)"
                        ),
                        timestamp=result.timestamp,
                    )
    history.record(result.endpoint_name, result.latency_ms, result.status_code, result.ok, result.attempts, result.timestamp)
    return drift_alert, baseline_ms, stdev_ms


def _linear_slope(values: list[float]) -> float:
    """Least-squares slope of `values` against 0..n-1 — ms increase per check."""
    n = len(values)
    xs = range(n)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def check_trend(result) -> Alert | None:
    """Detect a sustained upward trend via linear-regression slope over the last N checks.

    Complementary to check_drift: a z-score against an all-time baseline catches sudden
    point outliers, but a gradual climb gets absorbed into that same baseline as it
    happens (the stdev balloons right along with the drift), so the z-score alone can miss
    it after the first few checks. A slope check looks at recent trajectory instead of
    deviation from history, so it keeps firing for as long as the climb continues.
    """
    if not result.ok:
        return None
    values = history.recent_values(result.endpoint_name, config.TREND_WINDOW)
    if len(values) < config.TREND_MIN_SAMPLES:
        return None
    slope = _linear_slope(values)
    if slope > config.TREND_SLOPE_THRESHOLD_MS:
        return Alert(
            endpoint_name=result.endpoint_name,
            severity="warning",
            message=(
                f"{result.endpoint_name} latency trending up: +{slope:.1f}ms/check over the last "
                f"{len(values)} checks (currently {result.latency_ms:.0f}ms)"
            ),
            timestamp=result.timestamp,
        )
    return None


def log_alert(alert: Alert) -> None:
    ts = alert.timestamp.strftime("%H:%M:%S")
    print(f"[{ts}] ALERT ({alert.severity.upper()}) {alert.message}")


def now() -> datetime:
    return datetime.now(timezone.utc)
