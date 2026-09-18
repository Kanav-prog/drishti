# DRISHTI: Engineering Deep-Dive & Project Breakdown

This document provides a comprehensive, step-by-step technical breakdown of how DRISHTI was built, the libraries used, and the algorithmic "why" behind the project's architecture.

---

## 1. Project Genesis: Step-by-Step Breakdown

### Phase 1: The Data Foundation (Ingestion)
The first challenge was getting real-time data from Indian Railways.
1.  **The NTES Connector**: Built `backend/data/ntes_connector.py` to poll the National Train Enquiry System.
2.  **Physics Simulation**: Since real NTES data is sometimes delayed, we built a `telemetry_producer.py` to generate "physics-realistic" telemetry (speed, momentum, lat/lon) for training and demonstration.

### Phase 2: The Real-time Backbone (Streaming)
Railway safety requires sub-second latency.
1.  **Redis Streams**: Chosen for its <1ms latency. Ingested telemetry is pushed to a Redis stream.
2.  **FastAPI WebSockets**: Built a real-time hub that "listens" to Redis and "broadcasts" to the React frontend.

### Phase 3: The Intelligence Layer (ML)
This is where raw coordinates turn into safety alerts.
1.  **Anomaly Detection**: Implemented `Isolation Forest` to find "weird" train behavior.
2.  **Bayesian Inference**: Used `pgmpy` to model the probability of a crash given a specific set of symptoms (e.g., signal error + high speed).
3.  **Causal Graph**: Used `NetworkX` to map the actual physical tracks as a Directed Acyclic Graph (DAG) to see how delays propagate.

### Phase 4: The Command Center (Frontend)
A mission-critical UI for operators.
1.  **Geospatial Mapping**: Integrated `Leaflet.js` to render 1.03 lakh km of tracks.
2.  **State Management**: React + Hooks to handle the steady stream of WebSocket updates without UI stutter.

---

## 2. Library Inventory (The "Swiss Army Knife")

| Category | Library | Purpose |
| :--- | :--- | :--- |
| **Data Cleaning** | `Pandas` | Normalizing JSON, handling missing telemetry, time-series alignment. |
| **Numeric Logic** | `NumPy`, `SciPy` | Calculating vector distances between trains and signal bounds. |
| **Backend API** | `FastAPI` | Asynchronous, high-performance REST + WebSocket hub. |
| **ML Models** | `Scikit-learn` | Implementing the **Isolation Forest** anomaly detector. |
| **Network Logic** | `NetworkX` | Modeling the railway network as a physical graph. |
| **Probabilistic** | `pgmpy` | Running Bayesian propagation for risk scoring. |
| **Explainability** | `SHAP` | Explaining "why" a model flagged a specific train as high-risk. |
| **DevOps** | `Docker` | Containerizing every service for "Zero-Config" deployment. |

---

## 3. The Algorithms: Why these?

### A. Isolation Forest (Anomaly Detection)
*   **The Algorithm**: Instead of training the model on what a "normal" train looks like, it works by "isolating" outliers.
*   **Why**: Accidents are rare. If we only used "normal" data, we'd miss the "black swan" events. Isolation Forest is perfect because it requires *no labeled data* to find dangerous deviations.

### B. Causal DAG (Risk Propagation)
*   **The Algorithm**: A Directed Acyclic Graph where nodes are junctions and edges are tracks.
*   **Why**: Trains don't exist in a vacuum. A delay at New Delhi (NDLS) affects a train in Agra (AGC) 3 hours later. The DAG allows us to calculate the "Cascade Effect" across the entire network.

### C. Bayesian Networks
*   **The Algorithm**: A probabilistic graphical model that represents dependencies between dangerous conditions.
*   **Why**: Railway safety is rarely about one thing failing. It's usually "Signal failure" + "Fatigued driver" + "Night". Bayesian logic allows us to combine these into a single "Risk %".

---

## 4. DevOps: Step-by-Step Setup

### Step 1: Containerization (`Dockerfile`)
We wrap each service (API, Frontend, Producer) in its own Linux "bubble". This ensures that "it works on my machine" means "it works on the server."

### Step 2: Orchestration (`docker-compose.yml`)
One command to rule them all.
```bash
docker-compose up --build
```
This spins up:
-   **Redis**: Messaging hub.
-   **Postgres**: Long-term audit log.
-   **FastAPI**: The brain.
-   **Producer**: The heart (data generator).
-   **Frontend**: The eyes (UI).

### Step 3: Monitoring (Prometheus + Grafana)
We don't wait for things to crash.
1.  **Prometheus**: "Scrapes" the API every 15 seconds to check memory, CPU, and "Alerts Issued" count.
2.  **Grafana**: Turns these numbers into a beautiful operational dashboard for the DevOps team.

### Step 4: Production (Kubernetes)
For real-world scale, we use K8s.
1.  **Deployments**: Ensure 3 copies of the API are always running.
2.  **Services**: A Load Balancer to distribute traffic.
3.  **Ingress**: SSL termination to keep the data encrypted.

---
**DRISHTI is built for transparency.** Every library and algorithm was chosen to ensure that when an alert triggers, an operator can see exactly *which* data point caused it and *which* model flagged it.
