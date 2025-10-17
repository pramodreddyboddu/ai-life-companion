"""Metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_metrics_service
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/basic")
def basic_metrics(metrics_service: MetricsService = Depends(get_metrics_service)) -> dict[str, int]:
    """Return basic counter metrics as JSON."""

    return metrics_service.get_metrics()


@router.get("")
def prometheus_metrics(metrics_service: MetricsService = Depends(get_metrics_service)) -> Response:
    """Expose metrics in a Prometheus-friendly text format."""

    snapshot = metrics_service.get_metrics()
    counters = snapshot["counters"]
    histogram = snapshot["histogram"]

    lines = []
    lines.append("# TYPE ai_reminder_total counter")
    lines.append(f"ai_reminder_total{{status="scheduled"}} {counters.get('reminder_scheduled', 0)}")
    lines.append(f"ai_reminder_total{{status="sent"}} {counters.get('reminder_sent', 0)}")
    lines.append(f"ai_reminder_total{{status="canceled"}} {counters.get('reminder_canceled', 0)}")
    lines.append(f"ai_reminder_total{{status="error"}} {counters.get('reminder_error', 0)}")

    lines.append("# TYPE ai_reminder_latency_seconds histogram")
    cumulative = 0
    for bucket in sorted(histogram.keys()):
        bucket_value = histogram[bucket]
        cumulative += bucket_value
        bucket_label = bucket.split(":", 1)[1]
        lines.append(f"ai_reminder_latency_seconds_bucket{{le="{bucket_label}"}} {cumulative}")
    lines.append(f"ai_reminder_latency_seconds_count {counters.get('reminder_latency_count', 0)}")
    lines.append(f"ai_reminder_latency_seconds_sum {counters.get('reminder_latency_sum', 0)}")

    return Response("
".join(lines) + "
", media_type="text/plain; version=0.0.4")
