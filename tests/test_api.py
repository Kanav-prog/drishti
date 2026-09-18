"""
DRISHTI — FastAPI Endpoint Integration Tests
Tests: All REST endpoints, WebSocket connection, response schemas

Run: pytest tests/test_api.py -v
Requirements: API server running OR httpx AsyncClient (no server needed)
"""
import pytest
import asyncio
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use httpx TestClient for synchronous, no-server-needed testing
try:
    from httpx import AsyncClient
    from fastapi.testclient import TestClient
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from backend.api.server import app
    APP_AVAILABLE = True
except Exception as e:
    APP_AVAILABLE = False
    APP_ERROR = str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Skip guard
# ─────────────────────────────────────────────────────────────────────────────

skip_if_no_app = pytest.mark.skipif(
    not APP_AVAILABLE or not HTTPX_AVAILABLE,
    reason=f"FastAPI app not importable: {APP_ERROR if not APP_AVAILABLE else 'httpx not installed'}"
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    if not APP_AVAILABLE or not HTTPX_AVAILABLE:
        pytest.skip("FastAPI app not available")
    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_health_response_has_status(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert "status" in body

    def test_health_status_value(self, client):
        r = client.get("/api/health")
        body = r.json()
        assert body["status"] in ("ok", "healthy", "degraded", "starting", "online")


# ─────────────────────────────────────────────────────────────────────────────
# Network pulse endpoint
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestNetworkPulse:
    def test_pulse_returns_200(self, client):
        r = client.get("/api/network/pulse")
        assert r.status_code == 200

    def test_pulse_has_nodes(self, client):
        r = client.get("/api/network/pulse")
        body = r.json()
        assert "nodes" in body
        assert isinstance(body["nodes"], list)
        assert len(body["nodes"]) >= 30

    def test_pulse_has_zone_health(self, client):
        r = client.get("/api/network/pulse")
        body = r.json()
        assert "zone_health" in body
        assert isinstance(body["zone_health"], dict)

    def test_pulse_node_schema(self, client):
        r = client.get("/api/network/pulse")
        nodes = r.json()["nodes"]
        for node in nodes[:5]:  # spot-check first 5
            assert "id" in node, f"Node missing 'id': {node}"
            assert "name" in node, f"Node missing 'name': {node}"
            assert "stress_level" in node, f"Node missing 'stress_level': {node}"

    def test_content_type_json(self, client):
        r = client.get("/api/network/pulse")
        assert "application/json" in r.headers["content-type"]


# ─────────────────────────────────────────────────────────────────────────────
# Node filtering
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestNodeFiltering:
    def test_nodes_endpoint_200(self, client):
        r = client.get("/api/network/nodes")
        assert r.status_code == 200

    def test_zone_filter_returns_subset(self, client):
        """Filtering by zone should return fewer nodes than total."""
        all_nodes = client.get("/api/network/nodes").json()
        nr_nodes = client.get("/api/network/nodes?zone=NR").json()

        # NR should return a subset (could be empty if none tagged NR)
        all_count = len(all_nodes) if isinstance(all_nodes, list) else \
                    len(all_nodes.get("nodes", all_nodes))
        nr_count = len(nr_nodes) if isinstance(nr_nodes, list) else \
                   len(nr_nodes.get("nodes", nr_nodes))

        assert nr_count <= all_count, \
            f"Zone filter returned more nodes than total: {nr_count} > {all_count}"

    def test_invalid_zone_returns_empty_or_all(self, client):
        """Unknown zone should return empty list, not 500."""
        r = client.get("/api/network/nodes?zone=XXXXXXXXXINVALIDZONE")
        assert r.status_code in (200, 404)  # both acceptable


# ─────────────────────────────────────────────────────────────────────────────
# Cascade forecast endpoint
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestCascadeForecast:
    def test_cascade_ndls_200(self, client):
        r = client.get("/api/network/cascade/NDLS")
        assert r.status_code == 200

    def test_cascade_response_has_forecast(self, client):
        r = client.get("/api/network/cascade/NDLS")
        body = r.json()
        # Include all actual keys returned by get_cascade_forecast()
        has_forecast = any(k in body for k in (
            "cascade_forecast", "downstream", "t15", "impact",
            "affected_nodes", "nodes", "t15min", "t30min", "t2hr", "station"
        ))
        assert has_forecast, f"No forecast data in cascade response: {list(body.keys())}"

    def test_cascade_unknown_station_graceful(self, client):
        """Unknown station should return 404 or an empty forecast — never 500."""
        r = client.get("/api/network/cascade/XXXXXXUNKNOWN")
        assert r.status_code in (200, 404), \
            f"Expected 200 or 404 for unknown station, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zones endpoint
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestZonesEndpoint:
    def test_zones_200(self, client):
        r = client.get("/api/zones")
        assert r.status_code == 200

    def test_zones_has_data(self, client):
        r = client.get("/api/zones")
        body = r.json()
        # zones can be list or dict
        assert body is not None
        assert len(body) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Alerts endpoint
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestAlertsEndpoint:
    def test_alerts_history_200(self, client):
        r = client.get("/api/alerts/history")
        assert r.status_code in (200, 404)  # might not be populated yet

    def test_alerts_severity_filter(self, client):
        r = client.get("/api/alerts/history?severity=CRITICAL")
        assert r.status_code in (200, 404)

    def test_alerts_response_is_list_or_dict(self, client):
        r = client.get("/api/alerts/history")
        if r.status_code == 200:
            body = r.json()
            assert isinstance(body, (list, dict))


# ─────────────────────────────────────────────────────────────────────────────
# Error handling
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestErrorHandling:
    def test_unknown_api_route_graceful(self, client):
        """Unknown /api/ routes must not return 500 — either 404, 422, or 200 from SPA catch-all."""
        r = client.get("/api/this/route/does/not/exist")
        # Server has a catch-all SPA route; unknown API paths return 200 (SPA) or 404/422
        # The critical requirement is: no unhandled 500 errors
        assert r.status_code != 500, \
            f"Unhandled 500 on unknown API route: {r.text[:100]}"

    def test_catch_all_serves_frontend(self, client):
        """Unknown non-API routes should serve the React SPA (200), not 500.
        This is the intended behaviour for client-side routing."""
        r = client.get("/this/route/does/not/exist")
        # SPA catch-all: returns 200 with HTML or 404 if dist not built yet — never 500
        assert r.status_code in (200, 404), \
            f"Unexpected status for SPA catch-all: {r.status_code}"

    def test_no_unhandled_500_on_malformed_query(self, client):
        """Malformed query params should never cause 500."""
        bad_requests = [
            "/api/network/nodes?zone=" + "A" * 200,
            "/api/alerts/history?severity=XXXINVALID",
        ]
        for url in bad_requests:
            r = client.get(url)
            assert r.status_code != 500, \
                f"Unhandled 500 on: {url} → {r.text[:100]}"


# ─────────────────────────────────────────────────────────────────────────────
# Performance (response time smoke test)
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestPerformance:
    def test_health_responds_fast(self, client):
        import time
        start = time.time()
        client.get("/api/health")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Health endpoint too slow: {elapsed:.2f}s"

    def test_pulse_responds_under_3s(self, client):
        import time
        start = time.time()
        client.get("/api/network/pulse")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"Pulse endpoint too slow: {elapsed:.2f}s"

    def test_bayesian_scenarios_under_5s(self, client):
        """Bayesian inference for 4 scenarios must complete in < 5s total."""
        import time
        start = time.time()
        client.get("/api/bayesian/scenarios")
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Bayesian scenarios too slow: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────────────────────
# Bayesian Network endpoints (new in v7)
# ─────────────────────────────────────────────────────────────────────────────

@skip_if_no_app
class TestBayesianEndpoints:
    def test_scenarios_returns_200(self, client):
        """Bayesian scenarios endpoint must be reachable."""
        r = client.get("/api/bayesian/scenarios")
        assert r.status_code == 200

    def test_scenarios_has_scenarios_list(self, client):
        """Response must have a 'scenarios' key with a list."""
        r = client.get("/api/bayesian/scenarios")
        body = r.json()
        assert "scenarios" in body, f"Missing 'scenarios' key: {list(body.keys())}"
        assert isinstance(body["scenarios"], list)

    def test_scenarios_returns_four_cases(self, client):
        """Must return exactly 4 scenario results (or 0 if pgmpy offline)."""
        r = client.get("/api/bayesian/scenarios")
        scenes = r.json().get("scenarios", [])
        assert len(scenes) in (0, 4), f"Expected 0 or 4 scenarios, got {len(scenes)}"

    def test_scenario_has_p_accident(self, client):
        """Each non-error scenario result must have a p_accident in [0,1]."""
        r = client.get("/api/bayesian/scenarios")
        scenes = r.json().get("scenarios", [])
        for s in scenes:
            if "error" not in s:
                assert "p_accident" in s, f"Missing p_accident in scenario: {s}"
                assert 0.0 <= s["p_accident"] <= 1.0, \
                    f"p_accident out of range: {s['p_accident']}"

    def test_scenario_risk_levels_are_valid(self, client):
        """Risk level must be one of: LOW, MEDIUM, HIGH, CRITICAL."""
        valid = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        r = client.get("/api/bayesian/scenarios")
        scenes = r.json().get("scenarios", [])
        for s in scenes:
            if "error" not in s and "risk_level" in s:
                assert s["risk_level"] in valid, \
                    f"Invalid risk_level: {s['risk_level']}"

    def test_balasore_conditions_highest_risk(self, client):
        """Balasore-like scenario must have >= p_accident than Normal Operations."""
        r = client.get("/api/bayesian/scenarios")
        scenes = r.json().get("scenarios", [])
        if len(scenes) == 4 and all("p_accident" in s for s in scenes):
            normal   = scenes[0]["p_accident"]
            balasore = scenes[3]["p_accident"]
            assert balasore >= normal, \
                f"Balasore ({balasore}) should have >= risk than Normal ({normal})"

    def test_infer_endpoint_post(self, client):
        """POST /api/bayesian/infer must return 200 or 503 (if pgmpy offline)."""
        payload = {
            "delay_minutes": 45,
            "time_of_day": "NIGHT",
            "signal_cycle_time": 6.5,
            "maintenance_active": True,
            "centrality_rank": 85,
            "traffic_density": 0.9,
        }
        r = client.post("/api/bayesian/infer", json=payload)
        assert r.status_code in (200, 503), \
            f"Unexpected status from /api/bayesian/infer: {r.status_code}"

    def test_infer_response_schema(self, client):
        """If inference is live, response schema must be complete and valid."""
        payload = {
            "delay_minutes": 45,
            "time_of_day": "NIGHT",
            "signal_cycle_time": 6.5,
            "maintenance_active": True,
            "centrality_rank": 85,
        }
        r = client.post("/api/bayesian/infer", json=payload)
        if r.status_code == 200:
            body = r.json()
            assert "p_accident"  in body, "Missing p_accident"
            assert "risk_level"  in body, "Missing risk_level"
            assert "confidence"  in body, "Missing confidence"
            assert 0.0 <= body["p_accident"] <= 1.0, "p_accident out of [0,1]"
