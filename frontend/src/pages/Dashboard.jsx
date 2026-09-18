import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getCurrentTrains, getAlerts, getIngestionSummary, getHealth, getLiveStats } from '../api'

const ZONES = ['NR','CR','WR','ER','SR','SER','NFR','NWR','SCR']

const SEVERITY_MAP = {
  CRITICAL: { color: 'var(--red)',    bg: 'var(--red-bg)',    border: 'var(--red-border)' },
  HIGH:     { color: 'var(--orange)', bg: 'var(--orange-bg)', border: 'var(--orange-border)' },
  MEDIUM:   { color: 'var(--yellow)', bg: 'var(--yellow-bg)', border: 'var(--yellow-border)' },
  LOW:      { color: 'var(--green)',  bg: 'var(--green-bg)',  border: 'var(--green-border)' },
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, color, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-card-accent" style={{ background: color }} />
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color }}>{value ?? '—'}</div>
      {sub && <div className="stat-card-sub">{sub}</div>}
    </div>
  )
}

// ── Zone table row ────────────────────────────────────────────────────────────
function ZoneRow({ zone, count, max }) {
  const pct = max > 0 ? (count / max) * 100 : 0
  const stress = count > 15 ? 'HIGH' : count > 5 ? 'MEDIUM' : 'STABLE'
  const statusMap = { HIGH: 'var(--orange)', MEDIUM: 'var(--yellow)', STABLE: 'var(--green)' }

  return (
    <tr>
      <td><span className="mono" style={{ fontWeight: 600, fontSize: 12 }}>{zone}</span></td>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div className="score-bar-track" style={{ width: 100 }}>
            <div className="score-bar-fill" style={{ width: `${pct}%`, background: statusMap[stress] }} />
          </div>
          <span className="mono" style={{ fontSize: 12, color: 'var(--t3)', minWidth: 20 }}>{count}</span>
        </div>
      </td>
      <td>
        <span className={`badge badge-${stress.toLowerCase()}`}>{stress}</span>
      </td>
    </tr>
  )
}

// ── Alert row ─────────────────────────────────────────────────────────────────
function AlertFeedRow({ alert, onClick }) {
  const sev = alert.severity || 'LOW'
  const s = SEVERITY_MAP[sev] || SEVERITY_MAP.LOW
  const time = alert.timestamp
    ? new Date(alert.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })
    : '--:--'

  return (
    <tr onClick={onClick} style={{ cursor: 'pointer' }}>
      <td>
        <span className="mono" style={{ fontSize: 11, color: 'var(--t4)' }}>{time}</span>
      </td>
      <td style={{ maxWidth: 200 }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--t1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {alert.alert_type || 'System Alert'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--t4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {alert.node_id || alert.train_id || '—'} · {alert.zone || 'ALL'}
        </div>
      </td>
      <td><span className={`badge badge-${sev.toLowerCase()}`}>{sev}</span></td>
    </tr>
  )
}

// ── Dashboard page ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate()
  const [trains,    setTrains]    = useState([])
  const [alerts,    setAlerts]    = useState([])
  const [ingestion, setIngestion] = useState(null)
  const [live,      setLive]      = useState(false)
  const [sparkData, setSparkData] = useState([])
  const [liveStats, setLiveStats] = useState(null)

  const load = async () => {
    try {
      const [ts, als, ing, h, stats] = await Promise.all([
        getCurrentTrains(),
        getAlerts(30),
        getIngestionSummary(),
        getHealth(),
        getLiveStats(),
      ])
      setTrains(ts)
      setAlerts(als.slice(0, 15))
      setIngestion(ing)
      setLiveStats(stats)
      setSparkData(prev => {
        const next = [...prev, {
          time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
          value: ing.persisted || 0,
        }]
        return next.slice(-20)
      })
      setLive(h.status === 'ok')
    } catch { /* silent */ }
  }

  useEffect(() => { load(); const iv = setInterval(load, 8000); return () => clearInterval(iv) }, [])

  const critical = trains.filter(t => t.stress_level === 'CRITICAL').length
  const high     = trains.filter(t => t.stress_level === 'HIGH').length
  const alertCritical = liveStats?.alert_critical ?? alerts.filter(a => a.severity === 'CRITICAL').length
  const alertTotal    = liveStats?.alert_total    ?? alerts.length

  const zoneCounts = {}
  trains.forEach(t => { const z = t.zone || 'UNK'; zoneCounts[z] = (zoneCounts[z] || 0) + 1 })
  const maxZone = Math.max(1, ...Object.values(zoneCounts))

  const allZones = [...new Set([...ZONES, ...Object.keys(zoneCounts)])]

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <div className="page-header-title">Operations Command Centre</div>
            <div className={`live-pill ${live ? 'online' : 'offline'}`}>
              <span className="pulse-dot" style={{ background: live ? 'var(--green)' : 'var(--t4)', animation: live ? 'pulse-dot 2s ease-in-out infinite' : 'none' }} />
              {live ? 'LIVE' : 'OFFLINE'}
            </div>
          </div>
          <div className="page-header-sub">Indian Railways safety intelligence — real-time telemetry across all 16 zones</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => navigate('/alerts')}>View Alerts</button>
          <button className="btn btn-primary" onClick={() => navigate('/trains')}>Train Grid</button>
        </div>
      </div>

      <div className="container" style={{ paddingTop: 20 }}>

        {/* ── KPI Strip ── */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
          <StatCard label="Active Trains"   value={trains.length}  color="var(--blue)"   sub="Telemetry active" />
          <StatCard label="Critical Stress" value={critical}        color="var(--red)"    sub="Delay > 60 min" />
          <StatCard label="High Stress"     value={high}            color="var(--orange)" sub="Delay 30–60 min" />
          <StatCard label="Alert Events"    value={alertTotal}     color="var(--purple)" sub={`${alertCritical} critical`} />
          <StatCard label="Zones Monitored" value="16"             color="var(--green)"  sub="All IR zones" />
        </div>

        {/* ── Main grid ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 340px', gap: 16, marginBottom: 16 }}>

          {/* Zone coverage table */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Zone Coverage</span>
              <span className="card-label">IR NETWORK</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ZONE</th>
                    <th>TRAINS / LOAD</th>
                    <th>STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {allZones.map(z => (
                    <ZoneRow key={z} zone={z} count={zoneCounts[z] || 0} max={maxZone} />
                  ))}
                  {trains.length === 0 && (
                    <tr><td colSpan={3}>
                      <div className="empty-state" style={{ padding: '24px' }}>
                        <div className="empty-state-icon">⊡</div>
                        <div className="empty-state-title">No train data</div>
                        <div className="empty-state-sub">Telemetry producer initializing</div>
                      </div>
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pipeline sparkline */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Ingestion Pipeline</span>
              <span className="card-label">LAST 20 POLLS</span>
            </div>
            <div className="card-body">
              <div style={{ height: 140 }}>
                {sparkData.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={sparkData}>
                      <defs>
                        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="var(--blue)" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="var(--blue)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="time" tick={{ fill: 'var(--t4)', fontSize: 9 }} tickLine={false} axisLine={false} />
                      <YAxis hide />
                      <Tooltip
                        contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
                        labelStyle={{ color: 'var(--t3)' }}
                        itemStyle={{ color: 'var(--blue)' }}
                      />
                      <Area type="monotone" dataKey="value" name="Records" stroke="var(--blue)" strokeWidth={2} fill="url(#sparkGrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="empty-state" style={{ padding: 24 }}>
                    <div className="empty-state-sub">Collecting pipeline data…</div>
                  </div>
                )}
              </div>
              {ingestion && (
                <>
                  <div className="divider" />
                  <div style={{ display: 'flex', gap: 24 }}>
                    {[
                      { label: 'Received',  value: ingestion.received  || 0, color: 'var(--t2)' },
                      { label: 'Valid',     value: ingestion.valid     || 0, color: 'var(--blue)' },
                      { label: 'Persisted', value: ingestion.persisted || 0, color: 'var(--green)' },
                    ].map(m => (
                      <div key={m.label}>
                        <div className="mono" style={{ fontSize: 20, fontWeight: 800, color: m.color }}>{m.value.toLocaleString()}</div>
                        <div className="section-label" style={{ marginTop: 2 }}>{m.label}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* Quick links */}
              <div className="divider" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {[
                  { label: 'All Trains →',    to: '/trains',    },
                  { label: 'Network Map →',   to: '/network',   },
                  { label: 'AI Models →',     to: '/ai',        },
                  { label: 'Live Inference →',to: '/inference', },
                ].map(({ label, to }) => (
                  <button
                    key={to}
                    onClick={() => navigate(to)}
                    className="btn btn-ghost"
                    style={{ fontSize: 11.5, padding: '6px 10px', justifyContent: 'center' }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Live alert feed */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Live Alert Feed</span>
              <button onClick={() => navigate('/alerts')} className="btn btn-ghost" style={{ fontSize: 11, padding: '3px 8px' }}>
                All →
              </button>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 420 }}>
              {alerts.length > 0 ? (
                <table className="data-table">
                  <tbody>
                    {alerts.map((a, i) => (
                      <AlertFeedRow key={i} alert={a} onClick={() => navigate('/alerts')} />
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state">
                  <div style={{ fontSize: 24, marginBottom: 8, color: 'var(--green)' }}>✓</div>
                  <div className="empty-state-title">Network Stable</div>
                  <div className="empty-state-sub">No active alerts</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── System status bar ── */}
        <div className="card">
          <div className="card-body" style={{ padding: '12px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
              <span className="section-label">System Status</span>
              {[
                { label: 'FastAPI Backend', ok: live },
                { label: 'PostgreSQL DB',   ok: live },
                { label: 'Bayesian Engine', ok: live },
                { label: 'Alert Pipeline',  ok: live },
                { label: 'WebSocket Hub',   ok: live },
              ].map(({ label, ok }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: ok ? 'var(--green)' : 'var(--red)',
                    animation: ok ? 'pulse-dot 2.5s ease-in-out infinite' : 'none',
                  }} />
                  <span style={{ fontSize: 11.5, color: 'var(--t2)', fontWeight: 500 }}>{label}</span>
                </div>
              ))}
              <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--t4)' }}>
                CRIS / Ministry of Railways · AWS EC2 us-east-1
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
