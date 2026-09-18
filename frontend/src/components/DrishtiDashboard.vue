<!-- 
DRISHTI MAIN DASHBOARD
Visualizes: Real-time trains, Cascade propagation, Alerts with reasoning, ML predictions
-->

<template>
  <div class="dashboard-container">
    <!-- HEADER -->
    <header class="dashboard-header">
      <div class="header-left">
        <h1>🚂 DRISHTI Operations Control Center</h1>
        <p class="subtitle">Real-time Railway Intelligence | Cascade Prediction | ML Reasoning</p>
      </div>
      <div class="header-right">
        <div class="status-indicator" :class="systemStatus">
          {{ systemStatus === 'operational' ? '🟢 OPERATIONAL' : '🔴 ALERT MODE' }}
        </div>
        <span class="time">{{ currentTime }}</span>
      </div>
    </header>

    <!-- MAIN GRID -->
    <div class="dashboard-grid">
      
      <!-- LEFT: KEY METRICS -->
      <section class="metrics-panel">
        <h2>📊 Network Metrics</h2>
        
        <div class="metric-card critical">
          <span class="label">🚨 Critical Trains</span>
          <span class="value">{{ metrics.criticalTrains }}</span>
        </div>
        
        <div class="metric-card warning">
          <span class="label">⚠️ Stranded Passengers</span>
          <span class="value">{{ metrics.strandedPassengers.toLocaleString() }}</span>
        </div>
        
        <div class="metric-card info">
          <span class="label">📍 Trains Tracked</span>
          <span class="value">{{ metrics.trainsTracked }}</span>
        </div>
        
        <div class="metric-card">
          <span class="label">⏱️ Avg Delay</span>
          <span class="value">{{ metrics.avgDelay }} min</span>
        </div>
        
        <div class="metric-card">
          <span class="label">✅ On-Time %</span>
          <span class="value">{{ metrics.onTimePercentage }}%</span>
        </div>
        
        <div class="metric-card">
          <span class="label">🔍 Anomalies</span>
          <span class="value">{{ metrics.anomalies }}</span>
        </div>
      </section>

      <!-- CENTER: CASCADE VISUALIZATION -->
      <section class="cascade-panel">
        <h2>🌊 Cascade Propagation Network</h2>
        
        <div v-if="activeCascade" class="cascade-details">
          <div class="cascade-alert">
            <strong>🚨 ACTIVE CASCADE</strong>
            <span>{{ activeCascade.source }} → {{ activeCascade.depth }} junction chain</span>
            <span class="severity" :class="activeCascade.severity">{{ activeCascade.severity }}</span>
          </div>
          
          <div class="cascade-chain">
            <div v-for="(junction, index) in activeCascade.chain" :key="index" class="junction-node">
              <div class="node-label">{{ junction.name }}</div>
              <div class="node-delay">{{ junction.delay }}min</div>
              <div class="node-severity" :class="junction.severity"></div>
              <div v-if="index < activeCascade.chain.length - 1" class="arrow">→</div>
            </div>
          </div>
          
          <div class="cascade-stats">
            <p><strong>Affected Trains:</strong> {{ activeCascade.affectedTrains }}</p>
            <p><strong>Estimated Duration:</strong> {{ activeCascade.duration }}</p>
            <p><strong>Economic Impact:</strong> ₹{{ activeCascade.economicImpact.toLocaleString() }}</p>
          </div>
        </div>
        
        <div v-else class="cascade-clear">
          <span class="check">✓</span>
          <p>No active cascades detected</p>
        </div>
      </section>

      <!-- RIGHT: ZONE STATUS -->
      <section class="zones-panel">
        <h2>🗺️ Zone Status</h2>
        
        <div v-for="zone in zones" :key="zone.name" class="zone-card" :class="zone.status">
          <div class="zone-name">{{ zone.name }}</div>
          <div class="zone-status">{{ zone.status }}</div>
          <div class="zone-trains">{{ zone.trains }} trains</div>
        </div>
      </section>

    </div>

    <!-- BOTTOM: ALERTS WITH REASONING -->
    <section class="alerts-section">
      <h2>🔔 Unified Alerts & AI Reasoning</h2>
      
      <div class="alerts-container">
        <div v-for="alert in activeAlerts" :key="alert.id" class="alert-card" :class="alert.severity">
          
          <div class="alert-header">
            <strong>{{ alert.title }}</strong>
            <span class="severity-badge" :class="alert.severity">{{ alert.severity }}</span>
          </div>
          
          <p class="alert-description">{{ alert.description }}</p>
          
          <!-- REASONING CHAIN -->
          <details class="reasoning-details">
            <summary>📋 View AI Reasoning ({{ alert.reasons.length }} signals)</summary>
            
            <div class="reasoning-chain">
              <div v-for="(reason, idx) in alert.reasons" :key="idx" class="reason-item">
                <div class="reason-header">
                  <strong>{{ idx + 1 }}. {{ reason.model }}</strong>
                  <span class="confidence">{{ (reason.confidence * 100).toFixed(0) }}% confidence</span>
                </div>
                
                <p class="reason-category">
                  <strong>Signal:</strong> {{ reason.category }}
                </p>
                
                <div class="evidence-list">
                  <strong>Evidence:</strong>
                  <ul>
                    <li v-for="ev in reason.evidence" :key="ev">{{ ev }}</li>
                  </ul>
                </div>
                
                <p class="recommendation">
                  <strong>🎯 Recommendation:</strong> {{ reason.recommendation }}
                </p>
              </div>
            </div>
          </details>
          
          <div class="alert-impact">
            <strong>Impact:</strong>
            <span class="impact-value">{{ alert.impact.delay }} min delay</span>
            <span class="impact-value">{{ alert.impact.trains }} trains</span>
            <span class="impact-value">₹{{ alert.impact.economic.toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ML MODEL DASHBOARD -->
    <section class="ml-section">
      <h2>🤖 ML Model Insights</h2>
      
      <div class="ml-grid">
        <div class="ml-card">
          <h3>🔍 Isolation Forest</h3>
          <p class="metric">{{ mlModels.isolationForest.anomalies }} anomalies</p>
          <p class="confidence">Avg confidence: {{ (mlModels.isolationForest.confidence * 100).toFixed(0) }}%</p>
        </div>
        
        <div class="ml-card">
          <h3>🔮 LSTM Predictor</h3>
          <p class="metric">{{ mlModels.lstm.predictions }} predictions active</p>
          <p class="confidence">7-day accuracy: {{ mlModels.lstm.accuracy }}%</p>
        </div>
        
        <div class="ml-card">
          <h3>🌊 Cascade Simulator</h3>
          <p class="metric">{{ mlModels.cascade.active }} active cascades</p>
          <p class="confidence">Source: {{ mlModels.cascade.source }}</p>
        </div>
        
        <div class="ml-card">
          <h3>🔗 Correlation Engine</h3>
          <p class="metric">{{ mlModels.correlation.patterns }} patterns</p>
          <p class="confidence">Strongest: {{ (mlModels.correlation.strength * 100).toFixed(0) }}%</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
export default {
  name: 'DrishtiDashboard',
  data() {
    return {
      currentTime: '',
      systemStatus: 'operational',
      metrics: {
        criticalTrains: 3,
        strandedPassengers: 28750,
        trainsTracked: 127,
        avgDelay: 34,
        onTimePercentage: 71,
        anomalies: 47,
      },
      activeCascade: {
        source: 'NDLS',
        depth: 12,
        severity: 'critical',
        affectedTrains: 67,
        duration: '2.5 hours',
        economicImpact: 2872500,
        chain: [
          { name: 'NDLS', delay: 120, severity: 'emergency' },
          { name: 'CNB', delay: 95, severity: 'critical' },
          { name: 'MGS', delay: 78, severity: 'critical' },
          { name: 'PNBE', delay: 62, severity: 'warning' },
          { name: 'HWH', delay: 45, severity: 'warning' },
        ],
      },
      zones: [
        { name: 'NR', status: 'ALERT', trains: 67 },
        { name: 'WR', status: 'WARNING', trains: 22 },
        { name: 'ER', status: 'CAUTION', trains: 12 },
        { name: 'CR', status: 'NORMAL', trains: 8 },
        { name: 'SR', status: 'NORMAL', trains: 5 },
        { name: 'SCR', status: 'NORMAL', trains: 6 },
      ],
      activeAlerts: [
        {
          id: 'ALT-001',
          title: 'MAJOR CASCADE: Delhi → Lucknow → Gaya',
          description: 'Cascading delays detected at NDLS hub affecting 67 trains.',
          severity: 'critical',
          reasons: [
            {
              model: 'Cascade Simulator',
              confidence: 0.98,
              category: 'cascade',
              evidence: [
                '12 high-centrality junctions affected',
                'Average delay spike of 67 minutes',
              ],
              recommendation: 'Activate CASCADE_RESPONSE_PROTOCOL',
            },
            {
              model: 'Isolation Forest',
              confidence: 0.95,
              category: 'anomaly',
              evidence: [
                '47 trains with >5σ delay',
                '3 trains in EMERGENCY status',
              ],
              recommendation: 'Emergency diagnostics at NDLS signalling',
            },
          ],
          impact: { delay: 67, trains: 67, economic: 2872500 },
        },
        {
          id: 'ALT-002',
          title: 'ANOMALOUS SPEED: 22 trains @ 40% below capacity',
          description: 'Detected 22 trains running at 40% below normal speed in WR zone.',
          severity: 'warning',
          reasons: [
            {
              model: 'Isolation Forest',
              confidence: 0.92,
              category: 'anomaly',
              evidence: ['Speed deviation: -42%', 'Spatial clustering on BOMBAY-PUNE corridor'],
              recommendation: 'Check BOMBAY-PUNE section signalling',
            },
          ],
          impact: { delay: 84, trains: 22, economic: 315600 },
        },
      ],
      mlModels: {
        isolationForest: { anomalies: 47, confidence: 0.92 },
        lstm: { predictions: 12, accuracy: 87 },
        cascade: { active: 1, source: 'NDLS' },
        correlation: { patterns: 8, strength: 0.91 },
      },
    };
  },
  mounted() {
    this.updateTime();
    setInterval(this.updateTime, 1000);
    this.connectWebSocket();
  },
  methods: {
    updateTime() {
      const now = new Date();
      this.currentTime = now.toLocaleTimeString('en-IN', { hour12: true });
    },
    connectWebSocket() {
      // Connect to /ws/telemetry for real-time updates
      // const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
      // ws.onmessage = (event) => { /* update data */ };
    },
  },
};
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  background: #0f0f0f;
  color: #e0e0e0;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  min-height: 100vh;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #1e90ff;
}

.header-left h1 {
  margin: 0;
  font-size: 2em;
  color: #1e90ff;
}

.subtitle {
  margin: 5px 0 0 0;
  color: #888;
  font-size: 0.9em;
}

.header-right {
  display: flex;
  gap: 20px;
  align-items: center;
}

.status-indicator {
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.9em;
}

.status-indicator.operational {
  background: #004d00;
  color: #00ff00;
}

.time {
  font-size: 0.9em;
  color: #888;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

/* METRICS PANEL */
.metrics-panel {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.metrics-panel h2 {
  margin-top: 0;
  color: #1e90ff;
  border-bottom: 1px solid #333;
  padding-bottom: 10px;
}

.metric-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin: 8px 0;
  background: #252525;
  border-left: 3px solid #666;
  border-radius: 4px;
}

.metric-card.critical {
  border-left-color: #ff4444;
}

.metric-card.warning {
  border-left-color: #ffaa00;
}

.metric-card.info {
  border-left-color: #00aaff;
}

.metric-card .label {
  font-size: 0.85em;
  color: #aaa;
}

.metric-card .value {
  font-size: 1.3em;
  font-weight: bold;
  color: #fff;
}

/* CASCADE PANEL */
.cascade-panel {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.cascade-panel h2 {
  margin-top: 0;
  color: #1e90ff;
}

.cascade-alert {
  display: flex;
  gap: 10px;
  align-items: center;
  background: #2a1a1a;
  padding: 10px;
  border-left: 3px solid #ff4444;
  border-radius: 4px;
  margin-bottom: 15px;
}

.severity {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.8em;
  text-transform: uppercase;
}

.severity.critical {
  background: #ff4444;
  color: white;
}

.cascade-chain {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 15px 0;
  overflow-x: auto;
  padding: 10px;
}

.junction-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
  background: #252525;
  border-radius: 6px;
  white-space: nowrap;
  min-width: 80px;
}

.node-label {
  font-weight: bold;
  color: #1e90ff;
  font-size: 0.9em;
}

.node-delay {
  font-size: 0.85em;
  color: #ff4444;
  margin-top: 2px;
}

.node-severity {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 4px;
}

.node-severity.critical {
  background: #ff4444;
}

.node-severity.warning {
  background: #ffaa00;
}

.arrow {
  color: #666;
  font-size: 1.2em;
}

.cascade-stats {
  background: #252525;
  padding: 10px;
  border-radius: 4px;
  font-size: 0.9em;
}

.cascade-stats p {
  margin: 5px 0;
}

.cascade-clear {
  text-align: center;
  padding: 30px 10px;
  color: #666;
}

.check {
  font-size: 2em;
  color: #00ff00;
}

/* ZONES PANEL */
.zones-panel {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.zones-panel h2 {
  margin-top: 0;
  color: #1e90ff;
}

.zone-card {
  background: #252525;
  padding: 12px;
  margin: 8px 0;
  border-radius: 4px;
  border-left: 3px solid #666;
}

.zone-card.ALERT {
  border-left-color: #ff4444;
}

.zone-card.WARNING {
  border-left-color: #ffaa00;
}

.zone-card.CAUTION {
  border-left-color: #ffdd00;
}

.zone-card.NORMAL {
  border-left-color: #00ff00;
}

.zone-name {
  font-weight: bold;
  color: #fff;
}

.zone-status {
  font-size: 0.85em;
  color: #aaa;
  margin-top: 4px;
}

.zone-trains {
  font-size: 0.85em;
  color: #888;
}

/* ALERTS SECTION */
.alerts-section {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}

.alerts-section h2 {
  margin-top: 0;
  color: #1e90ff;
  border-bottom: 1px solid #333;
  padding-bottom: 10px;
}

.alerts-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 15px;
}

.alert-card {
  background: #252525;
  border-left: 3px solid #666;
  border-radius: 6px;
  padding: 15px;
}

.alert-card.critical {
  border-left-color: #ff4444;
}

.alert-card.warning {
  border-left-color: #ffaa00;
}

.alert-card.info {
  border-left-color: #00aaff;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.alert-header strong {
  color: #fff;
  font-size: 0.95em;
}

.severity-badge {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.75em;
  text-transform: uppercase;
  font-weight: bold;
}

.severity-badge.critical {
  background: #ff4444;
  color: white;
}

.severity-badge.warning {
  background: #ffaa00;
  color: black;
}

.alert-description {
  margin: 8px 0;
  font-size: 0.9em;
  color: #ccc;
}

.reasoning-details {
  margin: 12px 0;
  cursor: pointer;
}

.reasoning-details summary {
  color: #1e90ff;
  font-size: 0.85em;
  padding: 8px;
  background: #1a1a1a;
  border-radius: 3px;
  user-select: none;
}

.reasoning-chain {
  margin-top: 10px;
  background: #1a1a1a;
  padding: 10px;
  border-radius: 3px;
}

.reason-item {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #333;
}

.reason-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.reason-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.reason-header strong {
  color: #00aaff;
  font-size: 0.85em;
}

.confidence {
  background: #004d4d;
  color: #00ff00;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.75em;
}

.reason-category {
  margin: 4px 0;
  font-size: 0.85em;
  color: #aaa;
}

.evidence-list {
  margin: 8px 0;
  font-size: 0.85em;
}

.evidence-list strong {
  color: #ccc;
}

.evidence-list ul {
  margin: 4px 0 0 20px;
  pad: 0;
  list-style: disc;
}

.evidence-list li {
  margin: 2px 0;
  color: #999;
}

.recommendation {
  margin: 8px 0;
  font-size: 0.85em;
  color: #ffaa00;
}

.alert-impact {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #333;
  font-size: 0.85em;
}

.impact-value {
  background: #1a1a1a;
  padding: 3px 8px;
  border-radius: 3px;
  color: #aaa;
}

/* ML SECTION */
.ml-section {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
}

.ml-section h2 {
  margin-top: 0;
  color: #1e90ff;
  border-bottom: 1px solid #333;
  padding-bottom: 10px;
}

.ml-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 15px;
}

.ml-card {
  background: #252525;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 15px;
  text-align: center;
}

.ml-card h3 {
  margin-top: 0;
  color: #1e90ff;
  font-size: 0.95em;
}

.ml-card .metric {
  font-size: 1.5em;
  font-weight: bold;
  color: #fff;
  margin: 10px 0;
}

.ml-card .confidence {
  font-size: 0.85em;
  color: #888;
}

@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .alerts-container {
    grid-template-columns: 1fr;
  }
}
</style>
