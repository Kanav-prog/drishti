import { useState, useEffect, useCallback } from 'react'

const SEVERITY_COLOR = {
  CRITICAL: 'var(--red)',
  HIGH:     'var(--orange)',
  MEDIUM:   'var(--yellow)',
  LOW:      'var(--green)',
}
const SEVERITY_BG = {
  CRITICAL: 'var(--red-bg)',
  HIGH:     'var(--orange-bg)',
  MEDIUM:   'var(--yellow-bg)',
  LOW:      'var(--green-bg)',
}
const SEVERITY_BORDER = {
  CRITICAL: 'var(--red-border)',
  HIGH:     'var(--orange-border)',
  MEDIUM:   'var(--yellow-border)',
  LOW:      'var(--green-border)',
}

const MODEL_COLORS = {
  'Bayesian Network (pgmpy)':       'var(--purple)',
  'Bayesian Network':               'var(--purple)',
  'Isolation Forest (sklearn)':     'var(--orange)',
  'Isolation Forest':               'var(--orange)',
  'Causal DAG (doWhy/networkx)':    'var(--blue)',
  'Causal DAG (networkx)':          'var(--blue)',
  'Causal DAG':                     'var(--blue)',
  'DBSCAN Trajectory Clustering':   'var(--green)',
}

// ── Score bar ─────────────────────────────────────────────────────────────────
function ScoreBar({ score, threshold, color }) {
  const pct   = Math.min(score * 100, 100)
  const thPct = Math.min((threshold || 0.5) * 100, 100)
  const passes = score >= (threshold || 0.5)
  return (
    <div style={{ position: 'relative', height: 8, background: 'var(--bg-sunken)', borderRadius: 4, overflow: 'visible', marginTop: 4 }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 4 }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: passes ? (color || 'var(--blue)') : 'var(--border-med)',
          transition: 'width 600ms ease', borderRadius: 4,
        }} />
      </div>
      <div style={{
        position: 'absolute', top: -3, left: `${thPct}%`,
        width: 2, height: 14, background: 'var(--yellow)', borderRadius: 1, transform: 'translateX(-50%)',
      }} title={`Threshold: ${(threshold * 100).toFixed(0)}%`} />
    </div>
  )
}

// ── Model contribution row ────────────────────────────────────────────────────
function ModelRow({ contrib }) {
  const triggered = contrib.triggered
  const color = MODEL_COLORS[contrib.model] || 'var(--blue)'
  const statusColor = triggered ? 'var(--green)' : 'var(--t4)'

  return (
    <div style={{
      padding: '12px 16px',
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${triggered ? color : 'var(--border)'}`,
      borderRadius: 'var(--r-sm)',
      background: triggered ? 'var(--bg-raised)' : 'var(--bg-sunken)',
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--t1)' }}>{contrib.model}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--t4)', marginTop: 1 }}>
            Weight: {contrib.weight} · Threshold: {(contrib.threshold * 100).toFixed(0)}%
          </div>
        </div>
        <span style={{
          padding: '3px 10px', borderRadius: 4, fontSize: 9.5, fontWeight: 800,
          fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '0.06em',
          color: statusColor,
          background: triggered ? 'var(--green-bg)' : 'var(--bg-raised)',
          border: `1px solid ${triggered ? 'var(--green-border)' : 'var(--border)'}`,
        }}>
          {triggered ? '● TRIGGERED' : '○ PASS'}
        </span>
      </div>

      <ScoreBar score={contrib.score} threshold={contrib.threshold} color={color} />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--t4)', marginTop: 3, fontFamily: 'IBM Plex Mono, monospace' }}>
        <span>Score: {(contrib.score * 100).toFixed(1)}%</span>
        <span>Threshold: {(contrib.threshold * 100).toFixed(0)}%</span>
      </div>

      <p style={{ fontSize: 11.5, color: 'var(--t3)', lineHeight: 1.65, marginTop: 8, marginBottom: 6 }}>
        {contrib.description}
      </p>
      {contrib.factors?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {contrib.factors.map((f, i) => (
            <span key={i} style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 4,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              color: 'var(--t3)', fontFamily: 'IBM Plex Mono, monospace',
            }}>{f}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Decision card ─────────────────────────────────────────────────────────────
function DecisionCard({ decision, expanded, onToggle }) {
  const sev = decision.severity || 'LOW'
  const sevColor = SEVERITY_COLOR[sev] || 'var(--t3)'
  const ts = decision.timestamp ? new Date(decision.timestamp) : null
  const timeStr = ts ? ts.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '—'
  const dateStr = ts ? ts.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''

  const votes = decision.ensemble_votes ?? decision.final_decision?.confidence / 25 ?? 0
  const risk = decision.risk_score ?? decision.final_risk_score ?? 0

  return (
    <div className="card" style={{
      borderLeft: `4px solid ${sevColor}`,
      marginBottom: 10,
      transition: 'box-shadow var(--fast)',
    }}>
      {/* Header */}
      <div onClick={onToggle} style={{ padding: '12px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14 }}>

        {/* Severity + risk */}
        <div style={{
          width: 64, flexShrink: 0, padding: '8px', borderRadius: 'var(--r-sm)',
          background: SEVERITY_BG[sev], border: `1px solid ${SEVERITY_BORDER[sev]}`,
          textAlign: 'center',
        }}>
          <div className="mono" style={{ fontSize: 9, fontWeight: 800, color: sevColor, letterSpacing: '0.1em' }}>{sev}</div>
          <div className="mono" style={{ fontSize: 18, fontWeight: 800, color: sevColor, lineHeight: 1 }}>
            {(risk * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: 9, color: 'var(--t4)' }}>risk</div>
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {decision.train_name || decision.train_id} · {decision.station_code || decision.station_name || '—'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--t4)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <span>Train: {decision.train_id}</span>
            {decision.zone && <span>Zone: {decision.zone}</span>}
            {decision.verdict && <span>Verdict: {decision.verdict}</span>}
          </div>
        </div>

        {/* Model vote chips */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', maxWidth: 200, justifyContent: 'flex-end' }}>
          {decision.model_contributions?.map((m, i) => (
            <span key={i} style={{
              padding: '2px 7px', borderRadius: 4,
              background: m.triggered ? 'var(--green-bg)' : 'var(--bg-sunken)',
              border: `1px solid ${m.triggered ? 'var(--green-border)' : 'var(--border)'}`,
              color: m.triggered ? 'var(--green)' : 'var(--t4)',
              fontSize: 9.5, fontWeight: 700,
              fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '0.04em',
              whiteSpace: 'nowrap',
            }}>
              {m.triggered ? '✓' : '✗'} {(m.model || '').split(' ')[0]}
            </span>
          ))}
        </div>

        {/* Time */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div className="mono" style={{ fontSize: 12, color: 'var(--blue)', fontWeight: 600 }}>{timeStr}</div>
          <div style={{ fontSize: 10, color: 'var(--t4)' }}>{dateStr}</div>
        </div>

        <span style={{ color: 'var(--t4)', fontSize: 12, transition: 'transform 200ms', display: 'inline-block', transform: expanded ? 'rotate(180deg)' : '' }}>▼</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '16px 18px' }}>

          {/* Explanation */}
          {decision.explanation && (
            <p style={{ fontSize: 12.5, color: 'var(--t2)', lineHeight: 1.7, marginBottom: 14 }}>
              {decision.explanation}
            </p>
          )}

          {/* Risk formula */}
          <div style={{ padding: '12px 16px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', marginBottom: 14, border: '1px solid var(--border)' }}>
            <div className="section-label" style={{ marginBottom: 8 }}>Risk Formula</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--t1)' }}>
              <span style={{ color: 'var(--purple)' }}>0.40</span>×Bayesian
              {' + '}
              <span style={{ color: 'var(--orange)' }}>0.35</span>×IsoForest
              {' + '}
              <span style={{ color: 'var(--blue)' }}>0.25</span>×CausalDAG
              {' = '}
              <span style={{ color: sevColor, fontWeight: 800 }}>{(risk * 100).toFixed(1)}%</span>
            </div>
            <ScoreBar score={risk} threshold={0.5} color={sevColor} />
          </div>

          {/* Final decision */}
          {decision.final_decision && (
            <div style={{ marginBottom: 14, padding: '10px 14px', background: risk >= 0.5 ? 'var(--red-bg)' : 'var(--green-bg)', border: `1px solid ${risk >= 0.5 ? 'var(--red-border)' : 'var(--green-border)'}`, borderRadius: 'var(--r-sm)' }}>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: risk >= 0.5 ? 'var(--red)' : 'var(--green)' }}>
                {decision.final_decision.recommendation} · {decision.final_decision.confidence}% confidence
              </div>
              {decision.final_decision.reasoning && (
                <div style={{ fontSize: 11.5, color: 'var(--t3)', marginTop: 3 }}>{decision.final_decision.reasoning}</div>
              )}
            </div>
          )}

          {/* Model contributions */}
          {decision.model_contributions?.length > 0 && (
            <>
              <div className="section-label" style={{ marginBottom: 10 }}>Model Contributions</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                {decision.model_contributions.map((m, i) => <ModelRow key={i} contrib={m} />)}
              </div>
            </>
          )}

          {/* CRS Signature */}
          {decision.crs_signature && (
            <div style={{ padding: '12px 16px', background: 'var(--red-bg)', border: '1px solid var(--red-border)', borderRadius: 'var(--r-sm)' }}>
              <div style={{ fontWeight: 700, color: 'var(--red)', fontSize: 11.5, letterSpacing: '0.06em', marginBottom: 8 }}>
                ⚑ CRS Historical Signature Match
              </div>
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                {[
                  { label: 'Accident', value: decision.crs_signature.name },
                  { label: 'Date',     value: decision.crs_signature.date },
                  { label: 'Deaths',   value: decision.crs_signature.deaths, red: true },
                  { label: 'Pattern Match', value: `${decision.crs_signature.match_pct}%`, red: true },
                ].map(({ label, value, red }) => (
                  <div key={label}>
                    <div className="section-label" style={{ marginBottom: 3 }}>{label}</div>
                    <div className="mono" style={{ fontSize: 15, fontWeight: 800, color: red ? 'var(--red)' : 'var(--t1)' }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function AIDecisions() {
  const [data,    setData]    = useState({ decisions: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [live,    setLive]    = useState(false)
  const [expanded,setExpanded]= useState(null)
  const [filter,  setFilter]  = useState('ALL')

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/ai/decisions?limit=30')
      if (!res.ok) throw new Error('offline')
      const json = await res.json()
      setData(json)
      setLive(true)
    } catch { setLive(false) }
    setLoading(false)
  }, [])

  useEffect(() => { load(); const iv = setInterval(load, 10000); return () => clearInterval(iv) }, [load])

  const decisions = data.decisions ?? []
  const filtered = filter === 'ALL' ? decisions : decisions.filter(d => d.severity === filter)
  const counts = ['CRITICAL','HIGH','MEDIUM','LOW'].reduce((acc, s) => {
    acc[s] = decisions.filter(d => d.severity === s).length; return acc
  }, {})

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <div className="page-header-title">AI Decision Transparency</div>
            <div className={`live-pill ${live ? 'online' : 'offline'}`}>
              <span className="pulse-dot" style={{ background: live ? 'var(--green)' : 'var(--t4)', animation: live ? 'pulse-dot 2s ease-in-out infinite' : 'none' }} />
              {live ? 'LIVE INFERENCE' : 'OFFLINE'}
            </div>
          </div>
          <div className="page-header-sub">
            Full ML reasoning chain for every alert — see exactly why each model fired and how the ensemble voted
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingTop: 16 }}>

        {/* ── How decisions are made ── */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title">Ensemble Decision Methodology</span>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
              {[
                { label: 'Ensemble Voting', icon: '⊕', color: 'var(--purple)', value: '≥ 2 of 4 models must trigger for alert' },
                { label: 'Severity Rule',   icon: '⚑', color: 'var(--orange)', value: '≥ 75% risk → CRITICAL; ≥ 50% → HIGH' },
                { label: 'Risk Formula',    icon: '∑',  color: 'var(--blue)',   value: '0.40×Bayesian + 0.35×IsoForest + 0.25×CausalDAG' },
                { label: 'Data Sources',    icon: '◈',  color: 'var(--green)',  value: 'NTES live stream · CRS corpus · Synthetic simulation' },
              ].map(({ label, icon, color, value }) => (
                <div key={label} style={{ padding: '12px 14px', borderRadius: 'var(--r-sm)', background: 'var(--bg-sunken)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color, letterSpacing: '0.06em', marginBottom: 5 }}>
                    {icon} {label}
                  </div>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--t2)', lineHeight: 1.55 }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Stats strip ── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Total Decisions', value: data.total, color: 'var(--t1)' },
            { label: 'Critical',        value: counts.CRITICAL ?? 0, color: 'var(--red)' },
            { label: 'High',            value: counts.HIGH ?? 0,     color: 'var(--orange)' },
            { label: 'Medium',          value: counts.MEDIUM ?? 0,   color: 'var(--yellow)' },
            { label: 'Low',             value: counts.LOW ?? 0,      color: 'var(--green)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="stat-card" style={{ flex: 'none', minWidth: 'auto', padding: '10px 16px' }}>
              <div className="stat-card-label">{label}</div>
              <div className="mono" style={{ fontSize: 22, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
            </div>
          ))}
        </div>

        {/* ── Severity filters ── */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {['ALL','CRITICAL','HIGH','MEDIUM','LOW'].map(s => (
            <button
              key={s}
              className={`btn-filter ${filter === s ? `active-${s.toLowerCase()}` : ''}`}
              onClick={() => setFilter(s)}
            >
              {s}{s !== 'ALL' && counts[s] != null ? ` (${counts[s]})` : ''}
            </button>
          ))}
        </div>

        {/* ── Decision list ── */}
        {loading ? (
          <div className="empty-state">
            <div style={{ width: 28, height: 28, border: '2px solid var(--border)', borderTopColor: 'var(--blue)', borderRadius: '50%', animation: 'spin 0.8s linear infinite', marginBottom: 14 }} />
            <div className="empty-state-sub">Loading AI decisions…</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div style={{ fontSize: 32, color: 'var(--green)', marginBottom: 10 }}>✓</div>
            <div className="empty-state-title">No Decisions Yet</div>
            <div className="empty-state-sub">
              {live ? 'Backend is live — no alerts accumulated yet' : 'Backend API is offline — start the backend server'}
            </div>
          </div>
        ) : (
          <div>
            {filtered.map((d, i) => (
              <DecisionCard
                key={d.id ?? i}
                decision={d}
                expanded={expanded === i}
                onToggle={() => setExpanded(expanded === i ? null : i)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
