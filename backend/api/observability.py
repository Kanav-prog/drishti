from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter
from fastapi.responses import Response

# --- DRISHTI TELEMETRY ---
# Exposes DARPA-grade system metrics to Grafana

# Counters for tracking total volume
ALERTS_PROCESSED = Counter("drishti_alerts_total", "Total AI alerts generated across the network")
WS_MESSAGES_SENT = Counter("drishti_ws_messages_sent_total", "Total websocket payloads broadcasted")

# Gauges for tracking live network state (up/down)
ACTIVE_CONNECTIONS = Gauge("drishti_active_ws_connections", "Number of currently active controllers watching the stream")
CASCADING_NODES = Gauge("drishti_cascading_nodes_current", "Number of physical junctions currently in STRESSED or CRITICAL state")

# Router exposing /metrics for Prometheus to scrape
metrics_router = APIRouter()

@metrics_router.get("/metrics")
async def metrics():
    """Endpoint for Prometheus to scrape DRISHTI node hardware metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
