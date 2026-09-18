# ⚡ DRISHTI Quickstart — 5 Minute Setup

Get DRISHTI running with 100+ trains, cascade visualization, and AI alerts in 5 minutes.

---

## 🟢 1. PRE-FLIGHT CHECK (30 seconds)

```bash
# Verify you have Python 3.9+
python --version

# Verify you have the requirements installed
pip install fastapi uvicorn sqlalchemy psycopg2-binary requests

# Check you're in the drishti root directory
pwd  # should end with "/drishti"
```

---

## 🚀 2. START THE BACKEND (2 minutes)

### Option A: Full Demo (Recommended - Shows Everything)
```bash
# This generates 100+ trains, verifies data, and starts the backend
python run_demo.py
```

### Option B: Manual Steps (If run_demo.py doesn't work)

**Step 1:** Initialize database (30 seconds)
```bash
python backend/db/init_db.py
```

**Step 2:** Generate and ingest 100+ trains (30 seconds)
```bash
python scale_to_100_trains.py
```
You should see:
```
✅ Ingested: 127 trains across 6 zones

Zone Distribution:
   NR    : 22 trains
   WR    : 16 trains
   ER    : 20 trains
   CR    : 18 trains
   SR    : 14 trains
   SCR   : 12 trains
```

**Step 3:** Start the API server (30 seconds)
```bash
python -m uvicorn backend.main_app:app --host 0.0.0.0 --port 8000 --reload
```
You should see:
```
Uvicorn running on http://0.0.0.0:8000
```

---

## 📊 3. TEST THE SYSTEM (2 minutes)

Open these URLs in your browser or terminal to see the intelligence in action:

### Dashboard Summary
```
http://localhost:8000/api/dashboard/summary
```
Shows: Network status, real-time metrics, zones, health indicators

### Network Topology
```
http://localhost:8000/api/cascade/network-topology
```
Shows: All 51 junctions, edges, centrality scores

### Cascade Analysis
```
http://localhost:8000/api/cascade/analyze?source_junction=NDLS&initial_delay=120
```
Shows: Cascade chain from Delhi hub, affected junctions, predicted delays

### Unified Alerts
```
http://localhost:8000/api/alerts/unified?severity=critical
```
Shows: 3 critical alerts with AI reasoning from 4 different models

### API Documentation
```
http://localhost:8000/docs
```
Shows: Complete interactive API documentation (Swagger UI)

---

## 👀 4. WHAT TO LOOK FOR

When you run the system, you'll see:

### In Terminal Output
✅ 127 trains ingested  
✅ Cascade detected at NDLS (Delhi)  
✅ 67 trains affected  
✅ Backend running on port 8000

### In Browser (API Responses)
✅ Cascade chain: NDLS → CNB → LKO → ALD → MGS → PNBE → HWH  
✅ Alert with 4 ML models: Cascade Sim (98%), Isolation Forest (95%), LSTM (87%), Correlation (91%)  
✅ 51 junctions with centrality scores  
✅ Zone status: NR=ALERT, WR=WARNING, ER=CAUTION, others=NORMAL

---

## 🎨 5. (OPTIONAL) START THE FRONTEND

If you want to see the visual dashboard:

```bash
# In a NEW terminal
cd frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

You'll see:
- Real-time network map (D3 visualization)
- Cascade propagation animation
- Alert cards with AI reasoning
- Zone status board
- ML model insights

---

## 🔗 Quick Endpoints Reference

| What | URL |
|------|-----|
| **Swagger Docs** | http://localhost:8000/docs |
| **Dashboard** | http://localhost:8000/api/dashboard/summary |
| **Cascade Analysis** | http://localhost:8000/api/cascade/analyze?source_junction=NDLS&initial_delay=120 |
| **Network Map** | http://localhost:8000/api/cascade/network-topology |
| **Critical Alerts** | http://localhost:8000/api/alerts/unified?severity=critical |
| **Alert Reasoning** | http://localhost:8000/api/alerts/reasoning/ALT-2024-001 |
| **Zone Status** | http://localhost:8000/api/dashboard/operations |

---

## 💡 Try These Next

Once the system is running:

### 1. Trigger Different Cascade Sources
Try these different cascade starting points:
```
?source_junction=HWH&initial_delay=100   (Howrah - ER zone)
?source_junction=BOMBAY&initial_delay=90 (Mumbai - WR zone)
?source_junction=MAS&initial_delay=80    (Chennai - SR zone)
?source_junction=SC&initial_delay=110    (Hyderabad - SCR zone)
```

### 2. Filter Alerts by Severity
```
?severity=critical   (Most urgent)
?severity=warning    (Medium impact)
?severity=info       (FYI alerts)
```

### 3. Deep Dive into Alert Reasoning
```
http://localhost:8000/api/alerts/reasoning/ALT-2024-001
```
See the exact evidence chain for that alert

### 4. Generate More Trains
Edit `scale_to_100_trains.py` to change:
- Train count (increase TRAINS_ROSTER)
- Delay distributions
- Zone distribution

---

## ❌ Troubleshooting

### Port 8000 Already in Use
```bash
# Find what's using it
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
python -m uvicorn backend.main_app:app --port 8001
```

### Database Connection Failed
```bash
# For SQLite (default):
# Usually works out of the box

# For PostgreSQL:
# Make sure PostgreSQL is running and credentials match
python -c "from backend.db.session import SessionLocal; db = SessionLocal()"
```

### Module Not Found Error
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Make sure you're in the drishti directory
cd /path/to/drishti
```

### No Trains Showing Up
```bash
# Regenerate the dataset
python scale_to_100_trains.py

# Verify trains were ingested
python -c "from backend.db.session import SessionLocal; from backend.db.models import Train; db = SessionLocal(); print(f'{db.query(Train).count()} trains in database')"
```

---

## 📈 What This System Represents

| Component | Real System | Demo System |
|-----------|-----------|-----------|
| Daily Trains | 9,000+ | 100+ |
| Junctions | 51 (major) | 51 (same) |
| Zones | 16 | 16 |
| Network | Full IR topology | Full IR topology |
| Intelligence | Real-time | Simulated real-time |

**The demo scales to production with just data volume changes.**

---

## 🎯 Next Steps for Production

1. **Use `PRODUCTION_README.md`** for full deployment guide
2. **Configure PostgreSQL** instead of SQLite for database
3. **Set up Kafka** for high-volume telemetry ingestion
4. **Deploy with Docker/Kubernetes** (see `docker-compose.yml`)
5. **Add authentication** (API keys, JWT tokens)
6. **Set up monitoring** (Prometheus + Grafana in `deployment/`)

---

## 📞 Need Help?

- **Quick questions?** Check `PRODUCTION_README.md`
- **API details?** Go to `http://localhost:8000/docs`
- **ML details?** See `PHASE_4_5_COMPLETION_REPORT.md`
- **Files not working?** Run `python -m pytest tests/` to validate

---

**✅ Ready? Start with:**
```bash
python run_demo.py
```

**Then open:**
```
http://localhost:8000/api/dashboard/summary
http://localhost:8000/api/cascade/analyze?source_junction=NDLS&initial_delay=120
http://localhost:8000/api/alerts/unified?severity=critical
```

🚂 **Enjoy exploring DRISHTI!**
