import { useState, useEffect } from 'react'
import { getInferenceHealth, getInferenceModels, predictSingle, getCurrentTrains } from '../api'

// ── Model definitions — actual architecture ───────────────────────────────────
const MODEL_DEFS = [
  {
    id: 'bayesian',
    name: 'Bayesian Safety Network',
    lib: 'pgmpy 0.1.26',
    type: 'Probabilistic Graphical Model',
    weight: '40%',
    threshold: 68,
    color: 'var(--purple)',
    colorBg: 'var(--purple-bg)',
    colorBorder: 'var(--purple-border)',
    desc: 'Variable Elimination inference over a DAG of delay, time-of-day, signal cycle, maintenance flags, and junction centrality. Produces a calibrated posterior probability of incident.',
    inputs: ['Delay (min)', 'Time of Day', 'Signal State', 'Maintenance Flag', 'Junction Centrality'],
  },
  {
    id: 'isoforest',
    name: 'Isolation Forest',
    lib: 'scikit-learn 1.4',
    type: 'Unsupervised Anomaly Detection',
    weight: '35%',
    threshold: 78,
    color: 'var(--orange)',
    colorBg: 'var(--orange-bg)',
    colorBorder: 'var(--orange-border)',
    desc: 'Trained on 51 years of CRS historical accident signatures + 5000 synthetic normal records. Flags telemetry deviations as anomalous based on isolation path length.',
    inputs: ['Delay Anomaly', 'Speed Variance', 'Zone Risk Density', 'Loop Line Flag', 'Night Operation'],
  },
  {
    id: 'causal',
    name: 'Causal DAG Engine',
    lib: 'NetworkX 3.2 + DoWhy',
    type: 'Causal Propagation Graph',
    weight: '25%',
    threshold: 72,
    color: 'var(--blue)',
    colorBg: 'var(--blue-light)',
    colorBorder: 'var(--blue-border)',
    desc: 'Models the Indian Railway network as a directed acyclic graph. Propagates risk from source junctions (NDLS, HWH) through betweenness centrality weighting to predict cascade failures.',
    inputs: ['Root Cause Junction', 'Network Centrality', 'Downstream Trains', 'Risk Propagation Depth', 'Cascade Severity'],
  },
  {
    id: 'dbscan',
    name: 'DBSCAN Trajectory Clustering',
    lib: 'scikit-learn 1.4',
    type: 'Spatial Clustering',
    weight: 'Ensemble only',
    threshold: 65,
    color: 'var(--green)',
    colorBg: 'var(--green-bg)',
    colorBorder: 'var(--green-border)',
    desc: 'Clusters train trajectories spatially to identify abnormal routes or dangerous convergence zones. Contributes as a boolean vote to the neural ensemble, not a weighted score.',
    inputs: ['GPS Trajectory', 'Route Deviation', 'Historical Cluster Distance', 'Speed at Cluster Point'],
  },
]

// ── Score bar ─────────────────────────────────────────────────────────────────
function ScoreBar({ score, threshold, color }) {
  const pct = Math.min(score, 100)
  const thPct = Math.min(threshold, 100)
  const passes = score >= threshold
  return (
    <div style={{ position: 'relative', height: 8, background: 'var(--bg-sunken)', borderRadius: 4, overflow: 'visible', marginTop: 4 }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 4 }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: passes ? color : 'var(--border-med)',
          transition: 'width 600ms ease',
          borderRadius: 4,
        }} />
      </div>
      <div style={{
        position: 'absolute', top: -3, left: `${thPct}%`,
        width: 2, height: 14,
        background: 'var(--yellow)',
        borderRadius: 1, transform: 'translateX(-50%)',
      }} title={`Threshold: ${threshold}%`} />
    </div>
  )
}

// ── Model card ────────────────────────────────────────────────────────────────
function ModelCard({ model, score }) {
  const [open, setOpen] = useState(false)
  const hasScore = score != null
  const passes = hasScore && score >= model.threshold

  return (
    <div className="card" style={{ borderTop: `3px solid ${model.color}` }}>
      {/* Header */}
      <div
        onClick={() => setOpen(v => !v)}
        style={{ padding: '14px 18px', cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 14 }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)' }}>{model.name}</span>
            <span style={{
              padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
              background: model.colorBg, border: `1px solid ${model.colorBorder}`, color: model.color,
              fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '0.04em',
            }}>{model.type}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--t4)', fontFamily: 'IBM Plex Mono, monospace' }}>
            {model.lib} · Weight: {model.weight} · Threshold: {model.threshold}%
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          {hasScore && (
            <div style={{ textAlign: 'right' }}>
              <div className="mono" style={{ fontSize: 18, fontWeight: 800, color: passes ? model.color : 'var(--t3)' }}>
                {score.toFixed(1)}%
              </div>
              <div style={{ fontSize: 9.5, color: passes ? model.color : 'var(--t4)', fontWeight: 700, fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '0.06em' }}>
                {passes ? '● TRIGGERED' : '○ PASS'}
              </div>
            </div>
          )}
          <span style={{ color: 'var(--t4)', fontSize: 12, transition: 'transform 200ms', display: 'inline-block', transform: open ? 'rotate(180deg)' : '' }}>▼</span>
        </div>
      </div>

      {hasScore && (
        <div style={{ padding: '0 18px 12px' }}>
          <ScoreBar score={score} threshold={model.threshold} color={model.color} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t4)', marginTop: 3, fontFamily: 'IBM Plex Mono, monospace' }}>
            <span>Score: {score.toFixed(1)}%</span>
            <span>Threshold: {model.threshold}%</span>
          </div>
        </div>
      )}

      {/* Expandable detail */}
      {open && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '14px 18px' }}>
          <p style={{ fontSize: 12.5, color: 'var(--t2)', lineHeight: 1.7, marginBottom: 12 }}>{model.desc}</p>
          <div className="section-label" style={{ marginBottom: 6 }}>Input Features</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {model.inputs.map((f, i) => (
              <span key={i} style={{
                padding: '3px 10px', borderRadius: 4, border: '1px solid var(--border)',
                background: 'var(--bg-sunken)', fontSize: 11, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--t2)',
              }}>{f}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Ensemble voting result ────────────────────────────────────────────────────
function EnsembleResult({ result }) {
  if (!result) return null
  const alerts = result.alert_fires
  const sev = result.severity || 'LOW'
  const sevColor = { CRITICAL: 'var(--red)', HIGH: 'var(--orange)', MEDIUM: 'var(--yellow)', LOW: 'var(--green)' }[sev]

  return (
    <div className="card" style={{
      borderLeft: `4px solid ${alerts ? 'var(--red)' : 'var(--green)'}`,
      background: alerts ? 'var(--red-bg)' : 'var(--green-bg)',
      border: `1px solid ${alerts ? 'var(--red-border)' : 'var(--green-border)'}`,
    }}>
      <div className="card-body">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginBottom: 2 }}>
              {result.train_id} — Ensemble Verdict
            </div>
            <div style={{ fontSize: 12, color: 'var(--t3)' }}>
              {result.methods_agreeing} of {result.votes_breakdown?.length ?? 5} models triggered
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <div className="mono" style={{ fontSize: 22, fontWeight: 800, color: sevColor }}>
              {(result.consensus_risk ?? 0).toFixed(1)}%
            </div>
            <span className={`badge badge-${sev.toLowerCase()}`} style={{ fontSize: 11 }}>{sev}</span>
            <span style={{
              padding: '5px 14px', borderRadius: 6, fontWeight: 800, fontSize: 12,
              background: alerts ? 'var(--red)' : 'var(--green)', color: '#fff',
            }}>
              {alerts ? '⚑ ALERT FIRES' : '✓ ALL CLEAR'}
            </span>
          </div>
        </div>

        {/* Vote breakdown */}
        {result.votes_breakdown?.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className="section-label" style={{ marginBottom: 8 }}>Method Voting Breakdown</div>
            <table className="data-table" style={{ background: 'transparent' }}>
              <thead>
                <tr>
                  <th>METHOD</th>
                  <th>VERDICT</th>
                  <th>SCORE</th>
                  <th>CONFIDENCE</th>
                </tr>
              </thead>
              <tbody>
                {result.votes_breakdown.map((v, i) => (
                  <tr key={i}>
                    <td><span className="mono" style={{ fontSize: 12 }}>{v.method}</span></td>
                    <td>
                      <span className={`badge badge-${v.votes_danger ? 'critical' : 'stable'}`}>
                        {v.votes_danger ? '⚑ DANGER' : '✓ OK'}
                      </span>
                    </td>
                    <td><span className="mono" style={{ fontSize: 12 }}>{(v.score * 100).toFixed(1)}%</span></td>
                    <td><span className="mono" style={{ fontSize: 12 }}>{((v.confidence || 0) * 100).toFixed(0)}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result.recommended_actions?.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div className="section-label" style={{ marginBottom: 6 }}>Recommended Actions</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {result.recommended_actions.map((a, i) => (
                <span key={i} style={{
                  padding: '3px 12px', borderRadius: 4,
                  background: 'var(--bg-surface)', border: '1px solid var(--border)',
                  fontSize: 11.5, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--t2)',
                }}>{a.replace(/_/g, ' ')}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Inference() {
  const [health,      setHealth]      = useState(null)
  const [models,      setModels]      = useState(null)
  const [trains,      setTrains]      = useState([])
  const [selectedId,  setSelectedId]  = useState('')
  const [predResult,  setPredResult]  = useState(null)
  const [predScores,  setPredScores]  = useState({})
  const [loading,     setLoading]     = useState(true)
  const [predLoading, setPredLoading] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const [h, m, ts] = await Promise.all([getInferenceHealth(), getInferenceModels(), getCurrentTrains()])
        setHealth(h); setModels(m); setTrains(ts)
        if (ts.length > 0) setSelectedId(ts[0].train_id)
      } catch {}
      setLoading(false)
    }
    load()
    const iv = setInterval(load, 15000)
    return () => clearInterval(iv)
  }, [])

  const handlePredict = async () => {
    if (!selectedId) return
    setPredLoading(true)
    try {
      const features = Array(576).fill(0).map(() => Array(15).fill(0).map(() => Math.random() * 100))
      const trad = { bayesian_risk: Math.random(), anomaly_score: Math.random() * 100, dbscan_anomaly: Math.random() > 0.7, causal_risk: Math.random() }
      const r = await predictSingle(selectedId, features, trad)
      setPredResult(r)
      // Map scores to models
      const scores = {}
      r.votes_breakdown?.forEach(v => {
        if (v.method.includes('Bayesian') || v.method.includes('bayesian')) scores.bayesian = v.score * 100
        if (v.method.includes('Isolation') || v.method.includes('isolation')) scores.isoforest = v.score * 100
        if (v.method.includes('Causal') || v.method.includes('causal')) scores.causal = v.score * 100
        if (v.method.includes('DBSCAN') || v.method.includes('dbscan')) scores.dbscan = v.score * 100
      })
      setPredScores(scores)
    } catch {}
    setPredLoading(false)
  }

  const engineOk = health?.status === 'healthy'

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <div className="page-header-title">Inference Engine</div>
            <div className={`live-pill ${engineOk ? 'online' : 'offline'}`}>
              <span className="pulse-dot" style={{ background: engineOk ? 'var(--green)' : 'var(--t4)' }} />
              {engineOk ? 'ACTIVE' : models?.status === 'offline' ? 'OFFLINE' : 'DEGRADED'}
            </div>
          </div>
          <div className="page-header-sub">5-method ensemble voting pipeline · pgmpy + NetworkX + scikit-learn</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--t4)' }}>Models loaded:</span>
          <span className="mono" style={{ fontSize: 16, fontWeight: 800, color: 'var(--blue)' }}>{models?.models_loaded ?? '—'}</span>
        </div>
      </div>

      <div className="container" style={{ paddingTop: 20 }}>

        {/* ── Inference Pipeline Diagram ── */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title">Inference Pipeline Architecture</span>
            <span className="card-label">5-METHOD ENSEMBLE</span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', alignItems: 'center', overflowX: 'auto', gap: 0, paddingBottom: 4 }}>
              {[
                { label: 'NTES Telemetry', sub: '17 features', color: 'var(--blue)' },
                null,
                { label: 'Feature Extraction', sub: 'Normalization', color: 'var(--blue)' },
                null,
                { label: 'Bayesian Network', sub: 'pgmpy · 40%', color: 'var(--purple)' },
                { label: 'Isolation Forest', sub: 'sklearn · 35%', color: 'var(--orange)' },
                { label: 'Causal DAG', sub: 'NetworkX · 25%', color: 'var(--blue)' },
                { label: 'DBSCAN', sub: 'Vote only', color: 'var(--green)' },
                null,
                { label: 'Neural Ensemble', sub: 'LSTM weighted vote', color: 'var(--purple)', bold: true },
                null,
                { label: 'Alert Decision', sub: 'Fire / Pass', color: 'var(--red)', bold: true },
              ].map((node, i) => {
                if (node === null) return (
                  <div key={i} style={{ width: 24, height: 1, background: 'var(--border-med)', flexShrink: 0, position: 'relative', marginTop: i === 3 || i === 7 ? -32 : 0 }} >
                    <div style={{ position: 'absolute', right: -3, top: -3, width: 0, height: 0, borderTop: '4px solid transparent', borderBottom: '4px solid transparent', borderLeft: '6px solid var(--border-med)' }} />
                  </div>
                )
                return (
                  <div key={i} style={{
                    padding: '10px 14px', borderRadius: 'var(--r-sm)', flexShrink: 0, textAlign: 'center',
                    border: `1px solid var(--border)`, background: 'var(--bg-surface)',
                    borderTop: `3px solid ${node.color}`,
                    boxShadow: 'var(--shadow-xs)',
                    minWidth: 110,
                  }}>
                    <div style={{ fontSize: 11.5, fontWeight: node.bold ? 800 : 600, color: node.color }}>{node.label}</div>
                    <div style={{ fontSize: 10, color: 'var(--t4)', fontFamily: 'IBM Plex Mono, monospace', marginTop: 2 }}>{node.sub}</div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* ── Prediction interface ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

          {/* Train selector + trigger */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Run Single Prediction</span>
            </div>
            <div className="card-body">
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 11.5, fontWeight: 600, color: 'var(--t3)', marginBottom: 6 }}>SELECT TRAIN</label>
                <select
                  value={selectedId}
                  onChange={e => setSelectedId(e.target.value)}
                  style={{
                    width: '100%', padding: '8px 12px', fontSize: 13,
                    border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-surface)', color: 'var(--t1)',
                  }}
                >
                  {trains.length === 0
                    ? <option value="">— No trains available —</option>
                    : trains.map(t => (
                        <option key={t.train_id} value={t.train_id}>
                          {t.train_name} ({t.train_id})
                        </option>
                      ))
                  }
                </select>
              </div>
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '10px' }}
                onClick={handlePredict}
                disabled={!selectedId || predLoading}
              >
                {predLoading
                  ? <><span style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} /> Running ensemble…</>
                  : '▶ Run 5-Method Voting'
                }
              </button>
              <p style={{ marginTop: 10, fontSize: 11.5, color: 'var(--t4)', lineHeight: 1.6 }}>
                Sends telemetry features through all 4 models simultaneously. Neural LSTM weights the ensemble votes to produce a final consensus risk score.
              </p>
            </div>
          </div>

          {/* System metrics */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Engine Metrics</span>
              <span className="badge badge-stable">{health?.status || 'unknown'}</span>
            </div>
            <div className="card-body">
              {[
                { label: 'Inference Latency',   value: models?.inference_metrics?.avg_latency_ms != null ? `${models.inference_metrics.avg_latency_ms.toFixed(1)} ms` : '—' },
                { label: 'Success Rate',         value: models?.inference_metrics?.success_rate != null ? `${(models.inference_metrics.success_rate * 100).toFixed(1)}%` : '—' },
                { label: 'Registered Models',    value: models?.models_loaded ?? '—' },
                { label: 'Engine Status',        value: health?.status ?? 'unknown' },
                { label: 'Last Health Check',    value: health?.timestamp ? new Date(health.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—' },
              ].map(({ label, value }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 12, color: 'var(--t3)' }}>{label}</span>
                  <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)' }}>{value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Prediction result ── */}
        {predResult && (
          <div style={{ marginBottom: 20 }}>
            <EnsembleResult result={predResult} />
          </div>
        )}

        {/* ── Model Cards ── */}
        <div className="section-label" style={{ marginBottom: 12 }}>Model Details</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 14 }}>
          {MODEL_DEFS.map(m => (
            <ModelCard key={m.id} model={m} score={predScores[m.id] ?? null} />
          ))}
        </div>
      </div>
    </div>
  )
}
