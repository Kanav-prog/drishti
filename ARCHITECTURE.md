# 🏗️ DRISHTI System Architecture & Information Flow

This document visualizes how all components work together.

---

## 📊 High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    REAL-TIME TRAIN DATA SOURCES                      │
│  (In production: GPS trackers, signalling APIs, ticket systems)      │
└────────────────────┬─────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│              DATA INGESTION LAYER (backend/data/)                    │
│  • real_feed_connector.py    - Connects to train data sources       │
│  • quality_checker.py         - Validates data quality              │
│  • train_repository.py        - Ingests into database               │
└────────────────────┬─────────────────────────────────────────────────┘
                     ↓
┌──────────────────────────────────────────────────────────────────────┐
│                  DATABASE (PostgreSQL)                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Tables:                                                      │  │
│  │  • trains (127 records)                                     │  │
│  │  • train_telemetry (delay, speed, position, status)        │  │
│  │  • stations (51 critical junctions)                        │  │
│  │  • alerts (alert history + reasoning)                      │  │
│  │  • cascade_events (detected cascades)                      │  │
│  │  • ml_predictions (model outputs)                          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────────────────┘
                     ↓ (Read from DB)
     ┌───────────────┴───────────────────────────────┬────────────────┐
     ↓                                               ↓                ↓
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ ML ENGINES      │  │ REASONING        │  │ API ROUTES           │
│ Running in      │  │ ENGINE           │  │ (FastAPI)            │
│ Real-time       │  │ (alert_reasoning)│  │                      │
└─────────────────┘  └──────────────────┘  └──────────────────────┘
│                    │                    │
├─ Isolation Forest  ├─ Evidence Chain   ├─ /api/dashboard/*
├─ LSTM Predictor   ├─ Confidence Score ├─ /api/cascade/*
├─ Cascade Sim      ├─ Multi-model      ├─ /api/alerts/*
└─ Correlation      │  Consensus        └─ /ws/*
                    └──────────────────┘
     ↓                ↓                ↓
     └───────────────┬────────────────┴────────┬─────────────────┐
                     ↓                         ↓                 ↓
            ┌────────────────┐      ┌────────────────┐  ┌───────────────┐
            │ JSON/REST API  │      │ WebSocket      │  │ Real-time     │
            │ Responses      │      │ Streams        │  │ Telemetry     │
            └────────────────┘      └────────────────┘  └───────────────┘
                     ↓                      ↓
            ┌────────────────┐      ┌────────────────┐
            │ Vue.js         │      │ D3.js Network  │
            │ Components     │      │ Visualization  │
            │                │      │                │
            │ Dashboard      │      │ Cascade        │
            │ Alerts         │      │ Propagation    │
            │ Zone Status    │      │ Graphs         │
            └────────────────┘      └────────────────┘
```

---

## 🤖 ML Model Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     INPUT DATA (Current State)                   │
│  Train Position, Delay, Speed, Acceleration, Route, Zone, etc   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┬──────────────┐
        ↓                  ↓                  ↓              ↓
   ┌─────────┐      ┌──────────┐      ┌────────┐    ┌─────────────┐
   │ISOLATION│      │ LSTM     │      │CASCADE │    │CORRELATION │
   │ FOREST  │      │PREDICTOR │      │SIMLATOR│    │ ENGINE     │
   │         │      │          │      │        │    │            │
   │Detect   │      │Forecast  │      │Simulate│    │Find        │
   │anomalies│      │delays    │      │cascade │    │patterns    │
   │         │      │3hrs out  │      │prop    │    │multi-train │
   └────┬────┘      └────┬─────┘      └───┬────┘    └─────┬──────┘
        │                │                │               │
        │ Anomaly        │ Delay        │ Cascade      │ Correlation
        │ Score          │ Forecast      │ Chain        │ Strength
        │ (0.0-1.0)      │ (minutes)      │ (junctions)  │ (0.0-1.0)
        │                │                │               │
        └────────────────┬────────────────┴───────────────┘
                         ↓
        ┌────────────────────────────────┐
        │  ALERT REASONING ENGINE        │
        │  (Weighted Ensemble Voting)    │
        ├────────────────────────────────┤
        │ 1. Extract signals from models │
        │ 2. Weight by confidence        │
        │ 3. Correlate with incident DB  │
        │ 4. Generate unified alert      │
        │ 5. Attach evidence chains      │
        └────────────┬───────────────────┘
                     ↓
    ┌────────────────────────────────────┐
    │     UNIFIED ALERT OUTPUT           │
    ├────────────────────────────────────┤
    │ • Alert ID & Severity              │
    │ • Title & Description              │
    │ • Affected trains & junctions      │
    │ • Evidence from each model         │
    │ • Confidence scores                │
    │ • Recommended actions              │
    │ • Economic impact estimate         │
    └────────────────────────────────────┘
```

---

## 🔄 Cascade Propagation Algorithm

```
INPUT: A delay at junction J with value D minutes

STEP 1: BUILD NETWORK GRAPH
  ├─ Load 51 junctions + edges from database
  ├─ Compute centrality scores for each junction
  └─ Identify immediate neighbors of J

STEP 2: PROPAGATE CASCADE
  │
  ├─ Queue = [(J, D, depth=0)]
  │
  └─ For each junction in queue:
     ├─ Check if already visited (avoid cycles)
     ├─ Mark as visited
     ├─ Add to cascade chain with:
     │  ├─ Junction name
     │  ├─ Accumulated delay (= parent_delay * 0.85 + noise)
     │  ├─ Severity level (INFO/WARNING/CRITICAL/EMERGENCY)
     │  └─ Hops from source
     │
     ├─ For each neighboring junction:
     │  ├─ Calculate next_delay = current_delay * 0.85
     │  ├─ If hops < 4: Add to queue
     │  └─ Continue propagation
     │
     └─ Stop at depth 4 (limit propagation distance)

STEP 3: ANALYZE CASCADE
  ├─ Sort by hops (distance from source)
  ├─ Count junctions in each severity level
  ├─ Estimate total affected trains
  ├─ Calculate economic impact
  └─ Predict peak time

STEP 4: OUTPUT CASCADE CHAIN
  ├─ Source: NDLS (120 min delay, emergency)
  ├─ Hop 1: CNB (95 min delay, critical)
  ├─ Hop 2: LKO (78 min delay, critical)
  ├─ Hop 3: ALD (62 min delay, warning)
  ├─ Hop 4: MGS (45 min delay, warning)
  └─ Hop 5: PNBE (28 min delay, info)

Example cascade shows how delay signal weakens as it propagates.
```

---

## 📡 API Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│           FastAPI Routes (backend/main_app.py)      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ╔═══════════════════════════════════════════╗    │
│  ║ HEALTH & DIAGNOSTICS                     ║    │
│  ╠═══════════════════════════════════════════╣    │
│  ║ GET /health                              ║    │
│  ║ GET /api/test/generate-incident          ║    │
│  ║ GET /api/test/scale-to-trains            ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                     │
│  ╔═══════════════════════════════════════════╗    │
│  ║ CASCADE VISUALIZATION (cascade_viz.py)    ║    │
│  ╠═══════════════════════════════════════════╣    │
│  ║ GET /api/cascade/analyze                 ║    │
│  ║ GET /api/cascade/network-topology        ║    │
│  ║ GET /api/cascade/risk-matrix             ║    │
│  ║ WS /api/cascade/ws/live                  ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                     │
│  ╔═══════════════════════════════════════════╗    │
│  ║ ALERT REASONING (alert_reasoning.py)      ║    │
│  ╠═══════════════════════════════════════════╣    │
│  ║ GET /api/alerts/unified                  ║    │
│  ║ GET /api/alerts/reasoning/{id}           ║    │
│  ║ GET /api/alerts/recommendations/{id}     ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                     │
│  ╔═══════════════════════════════════════════╗    │
│  ║ DASHBOARD (main_app.py)                   ║    │
│  ╠═══════════════════════════════════════════╣    │
│  ║ GET /api/dashboard/summary                ║    │
│  ║ GET /api/dashboard/operations             ║    │
│  ║ GET /api/dashboard/ml-insights            ║    │
│  ║ WS /ws/telemetry                          ║    │
│  ╚═══════════════════════════════════════════╝    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🎨 Frontend Component Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    App.vue (Root)                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  DrishtiDashboard.vue (Main View)                 │ │
│  ├────────────────────────────────────────────────────┤ │
│  │                                                    │ │
│  │  Left:                Mid:              Right:    │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │ │
│  │  │  Metrics    │  │   Cascade    │  │  Zones   │ │ │
│  │  │  Panel      │  │   Viz        │  │  Status  │ │ │
│  │  │             │  │              │  │          │ │ │
│  │  │ • Critical  │  │ • Junction   │  │ • NR     │ │ │
│  │  │   trains    │  │   chain      │  │ • WR     │ │ │
│  │  │ • Stranded  │  │ • Delay      │  │ • ER     │ │ │
│  │  │   pax       │  │   propagation│  │ • CR     │ │ │
│  │  │ • Avg delay │  │ • Duration   │  │ • SR     │ │ │
│  │  │ • On-time % │  │ • Impact     │  │ • SCR    │ │ │
│  │  └─────────────┘  └──────────────┘  └──────────┘ │ │
│  │                                                    │ │
│  │  ┌──────────────────────────────────────────────┐ │ │
│  │  │    Alerts Section (Collapsible Cards)       │ │ │
│  │  ├──────────────────────────────────────────────┤ │ │
│  │  │ For each alert:                              │ │ │
│  │  │ ┌────────────────────────────────────────┐  │ │ │
│  │  │ │ ALERT-001: CRITICAL CASCADE            │  │ │ │
│  │  │ ├────────────────────────────────────────┤  │ │ │
│  │  │ │ Description: ...                       │  │ │ │
│  │  │ │                                        │  │ │ │
│  │  │ │ ▼ View AI Reasoning (3 signals)        │  │ │ │
│  │  │ │   ├─ Cascade Simulator (98%)           │  │ │ │
│  │  │ │   │  Evidence: 12 junctions, 67min avg│  │ │ │
│  │  │ │   │                                    │  │ │ │
│  │  │ │   ├─ Isolation Forest (95%)             │  │ │ │
│  │  │ │   │  Evidence: 47 trains >5σ, 3 emerg.│  │ │ │
│  │  │ │   │                                    │  │ │ │
│  │  │ │   └─ LSTM Predictor (87%)              │  │ │ │
│  │  │ │      Evidence: 2hr duration, peak PNBE│  │ │ │
│  │  │ │                                        │  │ │ │
│  │  │ │ Impact: 67min delay, ₹2,872,500       │  │ │ │
│  │  │ └────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────┘ │ │
│  │                                                    │ │
│  │  ┌──────────────────────────────────────────────┐ │ │
│  │  │    ML Insights (4 Model Outputs)           │ │ │
│  │  ├──────────────────────────────────────────────┤ │ │
│  │  │ ┌──────────────┐  ┌──────────────┐         │ │ │
│  │  │ │Isolation     │  │LSTM          │         │ │ │
│  │  │ │Forest        │  │Predictor     │         │ │ │
│  │  │ │47 anomalies  │  │12 pred'ns    │         │ │ │
│  │  │ │92% conf.     │  │87% accuracy  │         │ │ │
│  │  │ └──────────────┘  └──────────────┘         │ │ │
│  │  │ ┌──────────────┐  ┌──────────────┐         │ │ │
│  │  │ │Cascade Sim   │  │Correlation   │         │ │ │
│  │  │ │1 cascade     │  │8 patterns    │         │ │ │
│  │  │ │NDLS source   │  │91% strength  │         │ │ │
│  │  │ └──────────────┘  └──────────────┘         │ │ │
│  │  └──────────────────────────────────────────────┘ │ │
│  │                                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  NetworkVisualization.vue (D3 Graph)             │ │
│  ├────────────────────────────────────────────────────┤ │
│  │                                                    │ │
│  │  [Interactive D3 Network Diagram]                 │ │
│  │  • Nodes: 51 junctions (size = centrality)        │ │
│  │  • Links: Major routes                            │ │
│  │  • Red links: Active cascade chain                │ │
│  │  • Small circles: Train positions                 │ │
│  │  • Hover: Junction details                        │ │
│  │  • Zoom/Pan: Interact with graph                  │ │
│  │                                                    │ │
│  │  Controls: [Show Cascade] [Show Trains] [Reset]  │ │
│  │  Legend: Hubs | Junctions | Trains | Cascades    │ │
│  │                                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└──────────────────────────────────────────────────────────┘

Data Flow:
├─ DrishtiDashboard fetches from /api/dashboard/* (poll every 2s)
├─ DrishtiDashboard subscribes to /ws/telemetry (push updates)
├─ NetworkVisualization fetches from /api/cascade/network-topology
└─ All components update independently (Vue reactivity)
```

---

## 📂 File Dependency Graph

```
PRODUCTION DEMO
    │
    ├─ Main Entry
    │  └─ run_demo.py
    │     │
    │     ├─ scale_to_100_trains.py (Generate data)
    │     │  └─ backend/data/ (Data ingestion)
    │     │
    │     └─ backend/main_app.py (Start API server)
    │        │
    │        ├─ backend/api/cascade_viz.py (Cascade endpoints)
    │        │
    │        ├─ backend/api/alert_reasoning.py (Alert reasoning)
    │        │
    │        ├─ backend/db/models.py (Database models)
    │        ├─ backend/db/session.py (DB connection)
    │        │
    │        ├─ backend/intelligence/ml/
    │        │  ├─ incident_detector.py (Isolation Forest)
    │        │  └─ cascade_analyzer.py (Cascade logic)
    │        │
    │        └─ backend/inference/ml/
    │           ├─ cascade_simulator.py (Cascade propagation)
    │           └─ lstm_delay_predictor.py (LSTM forecasts)
    │
    ├─ Frontend
    │  ├─ frontend/src/App.vue
    │  │  └─ frontend/src/components/
    │  │     ├─ DrishtiDashboard.vue (Main dashboard)
    │  │     ├─ NetworkVisualization.vue (D3 graph)
    │  │     └─ (Other components)
    │  │
    │  └─ frontend/package.json (Dependencies)
    │
    └─ Documentation
       ├─ PRODUCTION_README.md (Comprehensive guide)
       ├─ QUICKSTART.md (5-minute setup)
       ├─ README.md (System overview)
       └─ This file (Architecture)
```

---

## 🔧 Configuration Points

```
┌────────────────────────────────────────────────────────┐
│          TUNABLE PARAMETERS (For Scaling)              │
├────────────────────────────────────────────────────────┤
│                                                        │
│ In scale_to_100_trains.py:                            │
│  • TRAINS_ROSTER = []        (Add more trains)        │
│  • Delay distributions       (Change delay percentages)│
│  • Speed ranges              (Faster/slower trains)    │
│                                                        │
│ In backend/api/cascade_viz.py:                        │
│  • Cascade depth limit       (propagation distance)    │
│  • Delay decay factor        (0.85 = 15% loss)        │
│  • Noise levels              (randomness in cascade)   │
│                                                        │
│ In backend/main_app.py:                               │
│  • Update frequencies        (polling intervals)       │
│  • WebSocket heartbeat       (connection keepalive)    │
│                                                        │
│ In database:                                          │
│  • Connection pooling        (max connections)         │
│  • Query timeouts            (max query duration)      │
│                                                        │
│ In frontend:                                          │
│  • Update poll interval      (dashboard refresh rate) │
│  • Animation speed           (D3 transitions)          │
│  • Colors & styling          (Theme customization)     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Performance Characteristics

```
Component                 | Latency  | Throughput      | Notes
─────────────────────────────────────────────────────────────────
Train Telemetry Ingest    |  <50ms   | 1000s/sec      | Batch ops
Database Query (single)   | 10-50ms  | 10k ops/sec    | Indexed
Cascade Simulation        | 200-500ms| ~1/sec         | Complex graph
ML Model Inference        | 100-300ms| 10s/sec        | CPU-bound
API Response (average)    | 100-200ms| 100-500 reqs/s | Network+compute
WebSocket Push            | <10ms    | Real-time      | No batching
Frontend Render           | <100ms   | 60 FPS         | Vue+D3 optimized
```

---

## 🔐 Data Security

```
┌──────────────────────────────────────────────────────────┐
│          SECURITY LAYERS (Production)                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Layer 1: Network                                         │
│  • SSL/TLS for all HTTP/WebSocket                        │
│  • API rate limiting (100 req/min default)               │
│  • IP whitelisting for operational endpoints             │
│                                                          │
│ Layer 2: Authentication                                  │
│  • API key validation for all requests                   │
│  • JWT tokens for WebSocket connections                  │
│  • Role-based access control (RBAC)                      │
│                                                          │
│ Layer 3: Database                                        │
│  • Encrypted at rest (TDE)                               │
│  • Connection SSL/TLS                                    │
│  • Parameterized queries (SQL injection prevention)      │
│                                                          │
│ Layer 4: Authorization                                   │
│  • View-level access control                             │
│  • Operational restrictions for non-admin users          │
│  • Audit logging for all changes                         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

**This architecture is designed to scale from 100 trains (demo) to 9000+ trains (production) with minimal code changes.**
