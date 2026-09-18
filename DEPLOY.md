# DRISHTI — Deployment Guide

> India's National Railway Grid Intelligence Platform  
> Production deployment on AWS EC2 · Automated via GitHub Actions

---

## 🏗️ Architecture Overview

```
Internet
    │
    ▼
EC2 Instance (44.216.1.62) : Port 80
    │
    ▼
┌─────────────────────────────────────┐
│  docker-compose.production.yml      │
│                                     │
│  ┌─────────────────┐                │
│  │ drishti-frontend│  :80 (Nginx)   │
│  │  React SPA      │                │
│  │  + Nginx Proxy  │                │
│  └────────┬────────┘                │
│           │ /api/* → :8000          │
│           │ /ws/*  → :8000          │
│  ┌────────▼────────┐                │
│  │  drishti-api    │  :8000         │
│  │  FastAPI v7.0   │                │
│  │  Bayesian Net   │                │
│  │  CascadeEngine  │                │
│  └────────┬────────┘                │
│           │                         │
│  ┌────────▼────────┐                │
│  │  redis:7-alpine │  :6379         │
│  │  (GPS feed sub) │                │
│  └─────────────────┘                │
└─────────────────────────────────────┘
           │
           ▼
  AWS RDS PostgreSQL
  (drishti-db-production.c2xe2oqy6mex.us-east-1.rds.amazonaws.com)
```

---

## 🚀 CI/CD Pipeline

**File:** `.github/workflows/production-pipeline.yml`

| Step | Job | Trigger |
|------|-----|---------|
| 1 | **Lint & Test** | pytest + eslint |
| 2 | **Frontend Build** | vite build check |
| 3 | **Build & Push Images** | → GHCR (ghcr.io/404avinash/drishti) |
| 4 | **Terraform Apply** | Provisions EC2 + RDS on AWS |
| 5 | **Deploy to EC2** | SSH → docker compose pull + up |

**Triggers:** Every push to `master`

---

## 🔑 Required GitHub Secrets

Go to **Settings → Secrets → Actions** and add:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `DB_USERNAME` | RDS master username |
| `DB_PASSWORD` | RDS master password |
| `EC2_SSH_KEY` | Private key for EC2 SSH (PEM format) |
| `EC2_SSH_PUB_KEY` | Corresponding public key |

---

## 🌐 Live URLs (Production)

| Service | URL |
|---------|-----|
| **Frontend Dashboard** | http://44.216.1.62 |
| **Landing Page** | http://44.216.1.62/ |
| **Operations Dashboard** | http://44.216.1.62/dashboard |
| **Network Intelligence** | http://44.216.1.62/network |
| **Live Train Tracker** | http://44.216.1.62/trains |
| **Alert Command Center** | http://44.216.1.62/alerts |
| **AI Brain** | http://44.216.1.62/ai |
| **System Health** | http://44.216.1.62/system |
| **Backend Health API** | http://44.216.1.62/api/health |
| **REST API Docs** | http://44.216.1.62/api/docs |

---

## 📡 API Endpoints (Backend)

All routes are proxied via Nginx from `/api/*` → FastAPI on `:8000`.

### Health & Stats
```
GET  /api/health                    System health check
GET  /api/stats                     Live stats (train counts, alerts)
```

### Trains (DB-backed)
```
GET  /api/trains/current            All active trains (array)
GET  /api/trains/:id/current        Single train state + latest telemetry
GET  /api/trains/:id/history        Telemetry history → { telemetry: [...] }
GET  /api/trains/station/:code      Trains at a station
GET  /api/trains/ingestion/summary  Pipeline stats → { total_records: {...} }
GET  /api/trains/coverage/zones     Zone distribution
```

### Alerts & Network
```
GET  /api/alerts/history            Alert buffer → { alerts: [...], total }
GET  /api/network/pulse             Full CascadeEngine state
GET  /api/network/nodes             Junction nodes (filterable)
GET  /api/network/cascade/:station  Cascade forecast from station
GET  /api/zones                     Zone health scores
```

### AI & ML
```
POST /api/bayesian/infer            Live P(accident) inference
POST /api/ml/anomaly/score          Isolation Forest scoring
POST /api/ml/explain                SHAP explainability
GET  /api/ml/drift/report           Model drift status
```

### WebSocket
```
WS   /ws/telemetry                  Live NTES telemetry stream
WS   /ws/alerts                     Live alert broadcast
```

---

## 🐳 Docker Images

Images are pushed to GitHub Container Registry (GHCR):

```
ghcr.io/404avinash/drishti/backend:latest
ghcr.io/404avinash/drishti/frontend:latest
```

Build locally:
```bash
# Backend
docker build -t drishti-api .

# Frontend
docker build -t drishti-frontend -f Dockerfile.frontend .
```

---

## 🔧 Local Development

```bash
# 1. Clone
git clone https://github.com/404Avinash/drishti.git
cd drishti

# 2. Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.api.server:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

> The frontend Vite dev server proxies `/api/*` requests to `localhost:8000` automatically.

---

## 🏗️ Terraform Infrastructure

```bash
cd terraform

# First-time setup (creates S3 backend)
bash ../scripts/setup_aws_backend.sh

# Deploy
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

Resources created:
- `aws_instance.drishti_ec2` — t3.small Ubuntu 22.04
- `aws_db_instance.drishti_rds` — PostgreSQL 15 (db.t3.micro)
- Security groups, key pairs, VPC defaults

---

## 🔍 Debugging

**Check containers on EC2:**
```bash
ssh -i keys ubuntu@44.216.1.62
cd /home/ubuntu/drishti
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f
docker compose -f docker-compose.production.yml logs drishti-api
```

**Manual redeploy:**
```bash
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d --remove-orphans
```

**Check API health:**
```bash
curl http://44.216.1.62/api/health | jq
```

---

## 📊 Frontend Architecture

```
frontend/
├── src/
│   ├── api.js            ← Normalized API client (shape adapters)
│   ├── App.jsx           ← React Router (8 routes)
│   ├── index.css         ← Design system (CSS vars, animations)
│   ├── components/
│   │   ├── Navbar.jsx         ← Top nav with live status
│   │   ├── StatCard.jsx       ← Animated KPI cards
│   │   ├── AlertBadge.jsx     ← Severity color pills
│   │   └── LiveIndicator.jsx  ← Pulsing live orb
│   └── pages/
│       ├── Home.jsx           ← Cinematic landing (particle canvas)
│       ├── Dashboard.jsx      ← Operations command center
│       ├── Network.jsx        ← Force graph (51 junctions)
│       ├── Trains.jsx         ← Live train tracker table
│       ├── TrainDetail.jsx    ← Per-train telemetry + charts
│       ├── Alerts.jsx         ← Timeline alert center
│       ├── Models.jsx         ← AI Bayesian brain
│       └── System.jsx         ← Infrastructure health
```

---

## ⚠️ Known Limitations

1. **Telemetry producer**: The separate telemetry producer container is not running in production.  
   The backend generates simulated alerts via its internal streaming loop (Bayesian + IsoForest).
   
2. **Train DB data**: `/api/trains/current` returns DB-backed trains.  
   If no telemetry has been ingested, this will return an empty array.  
   The WebSocket stream at `/ws/telemetry` always has live data.

3. **`started_at` field**: The backend `/api/health` doesn't expose `started_at`.  
   The System page uptime clock uses `/api/stats` → `uptime_seconds` instead.

---

*Last updated: April 2026 · DRISHTI v2.0 · Built with FastAPI + React + AWS*
