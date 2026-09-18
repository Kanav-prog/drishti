# DRISHTI Technical Architecture Summary

## Overview

DRISHTI is a real-time railway monitoring and intelligence system that aggregates multi-source Indian railway data, validates it through sophisticated quality checks, persists it in a relational database, and exposes it through REST APIs consumed by a React frontend.

---

## System Components

### 1. **Data Source Layer**

**Multi-Source Feed Aggregation:**
- **Rappid.in API** - Primary railway data source
- **IndiaRailInfo API** - Secondary feed for data validation
- **ErailIn API** - Tertiary feed for redundancy and fallback

**Purpose:** Ensures data availability and redundancy across multiple Indian railway information providers.

---

### 2. **Backend - Data Ingestion Pipeline**

#### **Real Feed Connector** (`backend/data/real_feed_connector.py`)
- Aggregates feeds from all three sources
- Implements fallback logic (if source 1 fails → try source 2 → try source 3)
- Fetches raw train telemetry, station info, and schedule data
- Returns quality-scored data to downstream processors

#### **Data Quality Checker** (`backend/data/quality_checker.py`)
Validates incoming data through three mechanisms:

1. **Deduplication (MD5 Hash)**
   - Computes MD5 fingerprint of entire train record
   - Identifies and filters duplicate observations
   
2. **Freshness Detection**
   - 30-minute staleness threshold
   - Marks data older than threshold as stale
   - Prevents persistence of outdated observations

3. **Anomaly Detection**
   - Detects unrealistic train delays (e.g., > 12 hours)
   - Flags impossible speeds (e.g., > 250 km/h)
   - Validates coordinate bounds (within India)
   - Identifies zone-boundary violations

#### **Phase 1 Ingestion Pipeline** (`backend/data/phase1_ingestion.py`)
- **Orchestrates** the entire data flow: fetch → validate → persist
- **Collects metrics** on data quality:
  - Records received (from all sources)
  - Records valid (after quality checks)
  - Records persisted (successfully stored)
- **Triggers metrics storage** in `data_ingestion_runs` table for monitoring

#### **Train Repository** (`backend/data/train_repository.py`)
- SQLAlchemy ORM abstraction layer
- Handles persistence of validated data to database
- Provides CRUD operations for Train, TrainTelemetry, and Station objects
- Encapsulates database logic from business rules

---

### 3. **Database Layer**

#### **ORM Framework**
- **SQLAlchemy** for ORM abstraction
- **SQLite** for development environments
- **PostgreSQL** for production deployments

#### **Core Tables**

| Table | Purpose |
|-------|---------|
| `users` | User authentication and authorization |
| `stations` | Railway station master data (7,000+ records) |
| `trains` | Train master data and real-time status |
| `train_telemetry` | Time-series telemetry (24-hour rolling history per train) |
| `data_ingestion_runs` | Metrics: received/valid/persisted per run |
| `audit_events` | Compliance and debugging trail |
| `schema_migrations` | Version control for database structure |

#### **Data Model Relationships**
```
Station (1) ──── (N) Train
Train (1) ──── (N) TrainTelemetry (24-hour history)
DataIngestionRun ←── Metrics from each pipeline execution
```

---

### 4. **Backend - API Layer**

#### **FastAPI Server** (`backend/api/server.py`)
- Modern async Python web framework
- **WebSocket support** for future real-time streaming
- Currently serves REST endpoints; WebSocket infrastructure ready
- Handles request routing, error handling, and response serialization

#### **Trains Router** (`backend/api/trains_router.py`)
Exposes 7 REST endpoints:

1. **GET /trains** - List all trains with optional filtering
2. **GET /trains/{train_id}** - Single train details
3. **GET /trains/{train_id}/telemetry** - 24-hour telemetry history
4. **GET /stations** - All stations (7,000+)
5. **GET /stations/{station_id}** - Single station details
6. **GET /ingestion-metrics** - Quality metrics from latest pipeline run
7. **POST /trains/search** - Advanced search with filters

All endpoints return JSON with pagination support.

---

### 5. **Frontend - React 18 + Vite**

#### **Architecture**
- **Framework:** React 18 with Hooks for state management
- **Build Tool:** Vite (fast bundling and dev server)
- **Styling:** CSS modules / Tailwind CSS
- **Transport:** HTTP polling (WebSocket ready for future)

#### **API Integration Layer** (`frontend/src/api.js`)
- **Centralizes** all backend API calls
- Provides single configuration point (base URL, timeouts, auth)
- Handles error responses globally
- Simplifies refactoring (e.g., switching from polling to WebSocket)

#### **Polling Engine**
- **Interval:** 5-15 seconds (configurable per view)
- Fetches updated train status, alerts, and telemetry
- Non-blocking with progressive updates
- Graceful degradation on network failures

#### **UI Components**

| Component | Purpose |
|-----------|---------|
| **Home** | System overview and quick stats |
| **Dashboard** | Real-time train status grid, metrics |
| **Alerts** | Anomalies, delays, quality warnings |
| **Map** | Geographic visualization of train locations |
| **Network** | Train network topology and route visualization |
| **TrainDetail** | Drill-down: single train with 24-hr history |

---

## Data Flow: End-to-End

### **Ingestion Cycle** (repeats every 60-300 seconds)

```
1. Real Feed Connector
   └─ Fetch from Rappid.in → India RailInfo → ErailIn (with fallback)
   └─ Output: Raw train records + metadata

2. Quality Checker
   └─ Hash-check each record (dedup filter)
   └─ Check timestamp (freshness filter)
   └─ Validate values (anomaly filter)
   └─ Output: Quality-scored records (pass/fail)

3. Phase 1 Pipeline
   └─ Orchestrate 1 & 2
   └─ Count: received/valid/persisted
   └─ Log metrics to data_ingestion_runs table

4. Train Repository
   └─ Persist validated records to DB
   └─ Maintain train_telemetry 24-hour rolling window
   └─ Update train status table

5. Metrics Storage
   └─ Record ingestion run stats
   └─ Enable dashboarding and SLA monitoring
```

### **Query Cycle** (5-15 second polling intervals)

```
Frontend → API Layer
          ↓
        Polling Engine (HTTP GET)
          ↓
FastAPI Server (backend/api/trains_router.py)
          ↓
SQLAlchemy ORM queries train_telemetry table
          ↓
Response: JSON train/station/telemetry data
          ↓
Frontend Components update state
          ↓
UI re-renders with latest observations
```

---

## Key Quality Assurance Features

### **Data Deduplication**
- **Mechanism:** MD5 hash of entire record
- **Prevents:** Multiple persistence of same observation
- **Storage:** Hash cached in database

### **Freshness Validation**
- **Threshold:** 30 minutes
- **Rule:** Discard observations older than 30 minutes from feed timestamp
- **Prevents:** Stale data contaminating historical queries

### **Anomaly Detection**
- **Delay anomalies:** Trains with delays > 12 hours flagged
- **Speed anomalies:** Speed > 250 km/h flagged as unrealistic
- **Coordinate validation:** Rejects GPS coordinates outside India bounds
- **Zone violations:** Ensures train zone consistency

### **Quality Scoring**
- Each record gets quality score (0-100)
- Influences persistence priority
- Exported in `/ingestion-metrics` endpoint

---

## Database Strategy

### **Development**
- SQLite for simplicity
- Single-file database
- Suitable for local development and testing

### **Production**
- PostgreSQL for scalability
- Supports concurrent connections
- ACID transactions across data_ingestion_runs
- Connection pooling for performance
- Backup and replication capabilities

### **Schema Evolution**
- Managed via `schema_migrations` table
- Version control integrated with ORM initialization
- Zero-downtime migrations on production

---

## Frontend State Management

**Current Approach:** Component-level state with context/Redux ready

**Polling Model:**
- Each component manages its own polling lifecycle
- Dashboard polls every 5 seconds (critical updates)
- Train detail polls every 15 seconds (less critical)
- Graceful error handling on network timeouts

**Future Enhancement:** WebSocket upgrade path exists via FastAPI WebSocket support

---

## Deployment Architecture

### **Development Stack**
- FastAPI dev server (port 8000)
- React dev server with Vite (port 5173)
- SQLite database (file-based)

### **Production Stack**
- FastAPI behind nginx reverse proxy
- React static build served via CDN/nginx
- PostgreSQL with connection pooling
- Docker containerized services
- Kubernetes orchestration (optional)

---

## Monitoring & Observability

### **Pipeline Metrics**
- **data_ingestion_runs table** tracks:
  - Timestamp of ingestion cycle
  - Records received from each source
  - Records passed quality checks
  - Records persisted to DB
  - Quality score distribution

### **API Metrics**
- Request latency per endpoint
- Error rates and types
- Cache hit rates (if caching added)

### **Database Metrics**
- Query performance on train_telemetry
- Index usage for station lookups
- Connection pool saturation

### **Frontend Metrics**
- API call success rates
- Polling interval adherence
- Component render performance

---

## Scalability Considerations

### **Data Ingestion**
- Parallel processing of multiple feed sources
- Batch validation (process N records at once)
- Async/await patterns to prevent blocking

### **Database**
- Indexing on `train_id`, `station_id`, `timestamp`
- Partitioning train_telemetry by date (24-hour retention)
- Read replicas for query load

### **Frontend**
- Pagination for large datasets (stations, trains)
- Virtual scrolling for long lists
- Code splitting by route with React lazy()

### **Network**
- API response compression (gzip)
- CDN distribution for static assets
- Caching headers on immutable data (station master)

---

## Security & Compliance

### **Authentication**  
- User table with hashed credentials
- JWT tokens for API authentication
- Session management for frontend

### **Audit Trail**
- audit_events table logs all mutations
- Timestamp and user tracking
- Enables compliance reporting

### **Data Validation**
- Input sanitization at API boundary
- Type checking via Pydantic models
- SQL injection prevention via ORM

---

## API Dependencies

### **Backend**
- `fastapi` - Web framework
- `sqlalchemy` - ORM
- `psycopg2` - PostgreSQL driver
- `pydantic` - Data validation

### **Frontend**
- `react@18` - UI framework
- `vite` - Build tool
- `axios` or `fetch` - HTTP client

---

## Summary

DRISHTI is a **three-tier architecture** with:

1. **Ingestion Tier:** Multi-source data aggregation with intelligent quality validation
2. **Data Tier:** Relational persistence with 24-hour rolling window for telemetry
3. **Presentation Tier:** Modern React frontend with API polling for near-real-time visualization

**Key Strengths:**
- ✅ Multi-source redundancy prevents single points of failure
- ✅ Quality-first approach ensures data integrity
- ✅ SQLAlchemy abstraction enables database flexibility
- ✅ REST + WebSocket-ready API layer
- ✅ Scalable architecture from dev to production

**Success Criteria:**
- 99%+ data freshness (< 30 min old)
- < 100ms P99 latency on API queries
- Zero duplicate records in database
- < 0.1% anomalies in railway data
