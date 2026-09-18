"""
DRISHTI Cascade Engine v2.0
Layer 2 + Layer 3: Live Ops Pulse + CRS Signature Intelligence

Loads the static Layer 1 graph → simulates NTES delay propagation →
runs SignatureMatcher on each node to produce real historical risk scores.
"""
import os
import json
import random
import time
import sys
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ── Import SignatureMatcher (Layer 3) ─────────────────────────────────────────
try:
    from backend.intelligence.signature_matcher import SignatureMatcher
    _matcher = SignatureMatcher()
    logger.info("[DRISHTI] SignatureMatcher loaded — 11 CRS signatures active")
except Exception as e:
    _matcher = None
    logger.warning(f"[DRISHTI] SignatureMatcher unavailable: {e}")

# ── Import AI anomaly engine (IsolationForest) ────────────────────────────────
try:
    from backend.alerts.ai_engine import ai as _ai
    logger.info("[DRISHTI] IsolationForest AI engine loaded")
except Exception as e:
    _ai = None
    logger.warning(f"[DRISHTI] AI engine unavailable: {e}")

# ── NTES Live Client ──────────────────────────────────────────────────────────
try:
    from backend.network.ntes_client import ntes as _ntes
except Exception:
    _ntes = None


class CascadeEngine:
    """
    DRISHTI Layer 2 & 3: Operations Pulse & Cascade Predictor.
    Loads the Layer 1 structure and simulates live NTES delays traversing it.
    """

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self.zone_health: Dict[str, dict] = {}
        self._step_count = 0

        self._load_graph()
        self._initialize_state()

    # ── Graph loading ─────────────────────────────────────────────────────────

    def _load_graph(self):
        """Load the pre-computed network_graph.json produced by generate_graph.py"""
        graph_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "public", "network_graph.json"
        )
        try:
            with open(graph_path, "r") as f:
                payload = json.load(f)

            graph = payload.get("graph", {})
            for node in graph.get("nodes", []):
                self.nodes[node["id"]] = {
                    "data": node,
                    "delay_minutes": 0,
                    "stress_level": "LOW",
                    "cascade_risk": 0.0,
                    "signature_match_pct": node.get("signature_match_pct", 0),
                    "signature_accident_name": node.get("signature_accident_name"),
                    "signature_date": node.get("signature_date"),
                    "signature_deaths": node.get("signature_deaths", 0),
                }

            self.edges = graph.get("links", [])
            logger.info(
                f"[CascadeEngine] Loaded {len(self.nodes)} nodes, {len(self.edges)} edges"
            )

        except Exception as e:
            logger.error(f"[CascadeEngine] Failed to load network graph: {e}")
            logger.error("  → Run: python scripts/generate_graph.py")

    # ── State initialisation ──────────────────────────────────────────────────

    def _initialize_state(self):
        zones = set()
        for node in self.nodes.values():
            z = node["data"].get("zone")
            if z:
                zones.add(z)

        for z in zones:
            self.zone_health[z] = {
                "score": 100,
                "status": "HEALTHY",
                "delayed_hubs": 0,
                "critical_hubs": 0,
                "avg_delay": 0,
            }

    # ── Simulation step ───────────────────────────────────────────────────────

    def step_simulation(self):
        """Advance the network state by one simulation tick."""
        if not self.nodes:
            return

        self._step_count += 1

        # ── 1. Inject new delays (NTES / statistical) ─────────────────────────
        # Pick 1-3 nodes to inject delay into this tick
        targets = random.sample(list(self.nodes.keys()), k=min(2, len(self.nodes)))
        for nid in targets:
            node = self.nodes[nid]
            centrality = node["data"].get("centrality", 0.3)

            # High-centrality nodes get injected with more frequent / larger delays
            inject_prob = centrality * 0.6
            if random.random() < inject_prob:
                # Source of delay: NTES live client or statistical fallback
                if _ntes:
                    delay = _ntes.poll_live_delay(nid)
                else:
                    # Weighted realistic dist: most trains on time, some late
                    weights = [55, 20, 12, 8, 5] if centrality < 0.6 else [40, 20, 15, 15, 10]
                    delay = random.choices([0, 10, 30, 60, 120], weights=weights)[0]

                if delay > 0:
                    node["delay_minutes"] = min(node["delay_minutes"] + delay, 300)

        # ── 2. Cascade propagation across edges ───────────────────────────────
        next_delays = {k: v["delay_minutes"] for k, v in self.nodes.items()}

        # Natural healing: network recovers ~2-4 min per tick
        for nid in next_delays:
            if next_delays[nid] > 0:
                next_delays[nid] = max(0, next_delays[nid] - random.randint(2, 5))

        # Cascade spread via edges
        for edge in self.edges:
            src = edge.get("source") or edge.get("from")
            tgt = edge.get("target") or edge.get("to")
            weight = edge.get("weight", 0.5)

            for u, v in [(src, tgt), (tgt, src)]:
                if u in self.nodes and v in self.nodes:
                    delay_u = self.nodes[u]["delay_minutes"]
                    if delay_u > 45:
                        # Cascade bleed proportional to edge weight and source delay
                        spread = int(delay_u * 0.08 * weight)
                        next_delays[v] = min(next_delays[v] + spread, 300)

        # ── 3. Apply state, compute stress + cascade risk + signature match ───
        zone_delay_sum: Dict[str, float] = {z: 0.0 for z in self.zone_health}
        zone_node_count: Dict[str, int] = {z: 0 for z in self.zone_health}

        for nid, node in self.nodes.items():
            delay = next_delays[nid]
            node["delay_minutes"] = delay
            centrality = node["data"].get("centrality", 0.3)

            # Stress classification
            if delay < 25:
                stress = "LOW"
            elif delay < 55:
                stress = "MEDIUM"
            elif delay < 110:
                stress = "HIGH"
            else:
                stress = "CRITICAL"
            node["stress_level"] = stress

            # Anomaly score via IsolationForest if available
            if _ai:
                is_night = time.localtime().tm_hour < 6 or time.localtime().tm_hour > 20
                try:
                    pred = _ai.predict_anomaly(
                        delay=delay,
                        goods=random.random() < 0.3,
                        night=is_night,
                        loop=random.random() < 0.2,
                        maintenance=False,
                    )
                    anomaly_score = pred.get("score", 50) / 100.0
                except Exception:
                    anomaly_score = delay / 300.0
            else:
                anomaly_score = min(delay / 180.0, 1.0)

            # Cascade risk = centrality × anomaly × stress multiplier
            stress_mult = {"LOW": 0.3, "MEDIUM": 0.55, "HIGH": 0.80, "CRITICAL": 1.0}[stress]
            node["cascade_risk"] = round(
                min(centrality * anomaly_score * stress_mult * 1.4, 1.0), 3
            )

            # ── Layer 3: CRS Signature Matching ───────────────────────────────
            if _matcher:
                try:
                    density = "HIGH" if centrality > 0.6 else ("MEDIUM" if centrality > 0.35 else "LOW")
                    alert_score = _matcher.score_current_state(
                        station_code=nid,
                        current_stress=delay,
                        current_delayed_trains=max(1, int(delay / 30)),
                        current_accumulated_delay=delay,
                        network_density=density,
                        maintenance_deferred=(delay > 80),
                    )
                    node["signature_match_pct"] = round(alert_score.score, 1)
                except Exception:
                    pass
            else:
                # Fallback: derive from stress level if no matcher
                base = {"LOW": 5, "MEDIUM": 22, "HIGH": 52, "CRITICAL": 75}[stress]
                node["signature_match_pct"] = min(
                    int(base + centrality * 20 + random.randint(-4, 4)), 98
                )

            # Zone aggregation
            z = node["data"].get("zone")
            if z and z in zone_delay_sum:
                zone_delay_sum[z] += delay
                zone_node_count[z] += 1

        # ── 4. Update zone health ─────────────────────────────────────────────
        for z in self.zone_health:
            count = zone_node_count.get(z, 0)
            if count > 0:
                avg = zone_delay_sum[z] / count
            else:
                avg = 0.0

            score = max(0, 100 - avg)
            self.zone_health[z]["score"] = round(score, 1)
            self.zone_health[z]["avg_delay"] = round(avg, 1)

            delayed = sum(
                1
                for n in self.nodes.values()
                if n["data"].get("zone") == z and n["stress_level"] in ("HIGH", "CRITICAL")
            )
            critical = sum(
                1
                for n in self.nodes.values()
                if n["data"].get("zone") == z and n["stress_level"] == "CRITICAL"
            )
            self.zone_health[z]["delayed_hubs"] = delayed
            self.zone_health[z]["critical_hubs"] = critical

            if score > 80:
                self.zone_health[z]["status"] = "HEALTHY"
            elif score > 55:
                self.zone_health[z]["status"] = "STRESSED"
            elif score > 30:
                self.zone_health[z]["status"] = "CRITICAL"
            else:
                self.zone_health[z]["status"] = "EMERGENCY"

    # ── State export ──────────────────────────────────────────────────────────

    @property
    def node_state(self) -> Dict:
        """Alias exposing internal nodes dict for test/debug access."""
        return self.nodes

    def get_state(self) -> Dict:
        """Returns the current full network intelligence pulse for WebSocket broadcast."""
        node_list = [
            {
                "id": k,
                "name": v["data"].get("name", k),
                "zone": v["data"].get("zone", ""),
                "centrality": round(v["data"].get("centrality", 0), 4),
                "risk_rank": v["data"].get("risk_rank", 0),
                "lat": v["data"].get("lat", 0),
                "lng": v["data"].get("lng", 0),
                "accident_count": v["data"].get("accident_count", 0),
                "accident_deaths": v["data"].get("accident_deaths", 0),
                "delay_minutes": v["delay_minutes"],
                "stress_level": v["stress_level"],
                "cascade_risk": v["cascade_risk"],
                "signature_match_pct": v.get("signature_match_pct", 0),
                "signature_accident_name": v.get("signature_accident_name"),
                "signature_date": v.get("signature_date"),
                "signature_deaths": v.get("signature_deaths", 0),
            }
            for k, v in self.nodes.items()
        ]
        # Top-level cascade summary: count of nodes at different risk tiers
        cascade_risk = {
            "critical_nodes": sum(1 for n in node_list if n["stress_level"] == "CRITICAL"),
            "high_nodes":     sum(1 for n in node_list if n["stress_level"] == "HIGH"),
            "max_cascade":    max((n["cascade_risk"] for n in node_list), default=0.0),
            "avg_cascade":    round(
                sum(n["cascade_risk"] for n in node_list) / max(1, len(node_list)), 3
            ),
        }
        return {
            "timestamp": time.time(),
            "step": self._step_count,
            "cascade_risk": cascade_risk,
            "nodes": node_list,
            "zone_health": self.zone_health,
        }

    def get_cascade_forecast(self, station_code: str) -> Dict:
        """Forecast downstream cascade impact for a specific node."""
        if station_code not in self.nodes:
            return {}

        source = self.nodes[station_code]
        delay = source["delay_minutes"]
        centrality = source["data"].get("centrality", 0.3)

        # Find adjacent nodes
        adjacent = []
        for edge in self.edges:
            src = edge.get("source") or edge.get("from")
            tgt = edge.get("target") or edge.get("to")
            weight = edge.get("weight", 0.5)
            if src == station_code and tgt in self.nodes:
                adjacent.append((tgt, weight))
            elif tgt == station_code and src in self.nodes:
                adjacent.append((src, weight))

        forecast = {
            "station": station_code,
            "station_name": source["data"].get("name", station_code),
            "current_delay": delay,
            "cascade_risk": source["cascade_risk"],
            "t15min": [],
            "t30min": [],
            "t2hr": [],
        }

        for adj_code, weight in adjacent[:8]:  # Top 8 adjacent
            adj_node = self.nodes[adj_code]
            adj_delay = adj_node["delay_minutes"]
            projected_15 = adj_delay + int(delay * 0.12 * weight)
            projected_30 = adj_delay + int(delay * 0.20 * weight)
            projected_2hr = adj_delay + int(delay * 0.35 * weight)

            entry = {
                "id": adj_code,
                "name": adj_node["data"].get("name", adj_code),
                "zone": adj_node["data"].get("zone", ""),
                "current_delay": adj_delay,
                "t15": projected_15,
                "t30": projected_30,
                "t2hr": projected_2hr,
                "risk": adj_node["cascade_risk"],
            }
            forecast["t15min"].append(entry)
            forecast["t30min"].append(entry)
            forecast["t2hr"].append(entry)

        forecast["trains_exposed"] = len(adjacent) * max(1, int(delay / 30))
        forecast["intervention"] = (
            f"Recommend holding 1 slow goods behind {station_code} "
            f"for 8 min to dissolve cascade at downstream nodes."
            if delay > 45
            else "No intervention required. Network flowing normally."
        )

        return forecast
