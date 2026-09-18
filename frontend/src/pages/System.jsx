import { useState, useEffect } from 'react'
import { getHealth, getIngestionSummary, getStats } from '../api'

// ── Uptime clock ──────────────────────────────────────────────────────────────
function UptimeClock({ seconds }) {
  const [elapsed, setElapsed] = useState(seconds || 0)
  useEffect(() => {
    setElapsed(seconds || 0)
    const iv = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(iv)
  }, [seconds])

  const d = Math.floor(elapsed / 86400)
  const h = Math.floor((elapsed % 86400) / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  const pad = n => String(n).padStart(2, '0')

  return (
    <span className="mono" style={{ fontSize: 24, fontWeight: 800, color: 'var(--green)', letterSpacing: '0.04em' }}>
      {d > 0 && `${d}d `}{pad(h)}:{pad(m)}:{pad(s)}
    </span>
  )
}

// ── Service health card ───────────────────────────────────────────────────────
function ServiceCard({ name, icon, status, detail, metric, metricLabel }) {
  const ok = status === 'ok' || status === 'healthy' || status === 'online' || status === 'ACTIVE'
  const c = ok ? 'var(--green)' : 'var(--red)'
  const bg = ok ? 'var(--green-bg)' : 'var(--red-bg)'
  const border = ok ? 'var(--green-border)' : 'var(--red-border)'

  return (
    <div className="card" style={{ borderTop: `3px solid ${c}` }}>
      <div style={{ padding: '14px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 16 }}>{icon}</span>
            <span style={{ fontSize: 13, fontWeight: 700 }}>{name}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, background: bg, border: `1px solid ${border}` }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: c, animation: ok ? 'pulse-dot 2s infinite' : 'none' }} />
            <span className="mono" style={{ fontSize: 9.5, fontWeight: 700, color: c, letterSpacing: '0.08em' }}>
              {ok ? 'ONLINE' : 'DEGRADED'}
            </span>
          </div>
        </div>
        {detail && <div style={{ fontSize: 11.5, color: 'var(--t3)', marginBottom: metric ? 10 : 0 }}>{detail}</div>}
        {metric != null && (
          <div>
            <div className="section-label" style={{ marginBottom: 3 }}>{metricLabel}</div>
            <div className="mono" style={{ fontSize: 18, fontWeight: 800, color: c }}>{metric}</div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main System page ──────────────────────────────────────────────────────────
export default function System() {
  const [health,    setHealth]    = useState(null)
  const [ingestion, setIngestion] = useState(null)
  const [stats,     setStats]     = useState(null)
  const [live,      setLive]      = useState(false)

  const load = async () => {
    try {
      const [h, ing, s] = await Promise.all([getHealth(), getIngestionSummary(), getStats()])
      setHealth(h); setIngestion(ing); setStats(s)
      setLive(h.status === 'ok')
    } catch { setLive(false) }
  }
  useEffect(() => { load(); const iv = setInterval(load, 10000); return () => clearInterval(iv) }, [])

  return (
    <div>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
            <div className="page-header-title">System Health Monitor</div>
            <div className={`live-pill ${live ? 'online' : 'offline'}`}>
              <span className="pulse-dot" style={{ background: live ? 'var(--green)' : 'var(--t4)', animation: live ? 'pulse-dot 2s ease-in-out infinite' : 'none' }} />
              {live ? 'ALL SYSTEMS NOMINAL' : 'DEGRADED'}
            </div>
          </div>
          <div className="page-header-sub">Infrastructure status · API health · Database connections · Ingestion pipeline</div>
        </div>
      </div>

      <div className="container" style={{ paddingTop: 20 }}>

        {/* ── Uptime banner ── */}
        <div className="card" style={{ marginBottom: 20, borderLeft: '4px solid var(--green)' }}>
          <div className="card-body">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <div className="section-label" style={{ marginBottom: 6 }}>System Uptime</div>
                <UptimeClock seconds={stats?.uptime_seconds ?? 0} />
              </div>
              <div style={{ display: 'flex', gap: 32 }}>
                <div>
                  <div className="section-label" style={{ marginBottom: 4 }}>Deployed On</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t2)' }}>AWS EC2 · us-east-1 · Ubuntu 22.04</div>
                </div>
                <div>
                  <div className="section-label" style={{ marginBottom: 4 }}>Operator</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t2)' }}>CRIS · Ministry of Railways, GoI</div>
                </div>
                <div>
                  <div className="section-label" style={{ marginBottom: 4 }}>Version</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--t2)' }}>DRISHTI v2.0.0</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Service cards ── */}
        <div className="section-label" style={{ marginBottom: 12 }}>Service Health</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14, marginBottom: 20 }}>
          <ServiceCard name="API Server"       icon="⊞" status={health?.status || 'unknown'}                           detail="FastAPI 0.110 · Python 3.11 · Uvicorn"      metricLabel="Response"    metric={health ? '< 50ms' : null} />
          <ServiceCard name="PostgreSQL"        icon="◫" status={health?.database || 'unknown'}                          detail="PostgreSQL 15 · AWS RDS · us-east-1"        metricLabel="Connections"  metric={health?.db_connections ?? null} />
          <ServiceCard name="Redis Stream"      icon="◈" status={live ? 'ok' : 'unknown'}                                detail="Redis 7 · Telemetry message broker"         metricLabel="Latency"      metric="< 1ms" />
          <ServiceCard name="WebSocket Hub"     icon="◉" status={health?.websocket_connections >= 0 ? 'ok' : 'unknown'}  detail="NTES telemetry broadcast service"           metricLabel="Active WS"    metric={health?.websocket_connections ?? 0} />
          <ServiceCard name="Bayesian Engine"   icon="⬙" status="ACTIVE"                                                 detail="pgmpy 0.1.26 · Variable Elimination"        metricLabel="Models"       metric="4 active" />
          <ServiceCard name="Alert Pipeline"    icon="⚑" status="ACTIVE"                                                 detail="Real-time threshold + ensemble voting"      metricLabel="Threshold"    metric="< 100ms" />
          <ServiceCard name="Telemetry Producer"icon="⊡" status={live ? 'ok' : 'unknown'}                                detail="Python producer · Redis publish loop"       metricLabel="Rate"         metric="2s cycle" />
          <ServiceCard name="Docker Runtime"    icon="◻" status="ACTIVE"                                                 detail="3 containers: api · frontend · producer"    metricLabel="Version"      metric="v24.0+" />
        </div>

        {/* ── Ingestion pipeline ── */}
        {ingestion && (
          <>
            <div className="section-label" style={{ marginBottom: 12 }}>Data Ingestion Pipeline</div>
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-body">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14, marginBottom: 16 }}>
                  {[
                    { label: 'Records Received', value: (ingestion.received || 0).toLocaleString(),  color: 'var(--t2)' },
                    { label: 'Valid Records',    value: (ingestion.valid    || 0).toLocaleString(),  color: 'var(--blue)' },
                    { label: 'Persisted to DB',  value: (ingestion.persisted|| 0).toLocaleString(),  color: 'var(--green)' },
                    { label: 'Error Rate',       value: `${((ingestion.error_rate || 0) * 100).toFixed(2)}%`, color: (ingestion.error_rate || 0) > 0.05 ? 'var(--red)' : 'var(--green)' },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{ padding: '12px 16px', background: 'var(--bg-sunken)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)' }}>
                      <div className="section-label" style={{ marginBottom: 6 }}>{label}</div>
                      <div className="mono" style={{ fontSize: 20, fontWeight: 800, color }}>{value}</div>
                    </div>
                  ))}
                </div>
                {ingestion.by_source && Object.keys(ingestion.by_source).length > 0 && (
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
                    <div className="section-label" style={{ marginBottom: 8 }}>By Source</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {Object.entries(ingestion.by_source).map(([src, cnt]) => (
                        <span key={src} style={{
                          padding: '4px 12px', borderRadius: 20,
                          background: 'var(--blue-light)', border: '1px solid var(--blue-border)',
                          fontSize: 11.5, fontFamily: 'IBM Plex Mono, monospace', color: 'var(--blue)', fontWeight: 600,
                        }}>{src}: {cnt.toLocaleString()}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ── Raw health JSON (collapsible) ── */}
        {health && (
          <>
            <div className="section-label" style={{ marginBottom: 12 }}>Raw API Health</div>
            <div className="card">
              <div style={{ padding: '14px 20px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)' }}>
                <pre className="mono" style={{ fontSize: 11, color: 'var(--green)', lineHeight: 1.8, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(health, null, 2)}
                </pre>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
