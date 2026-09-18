import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import AlertBadge from '../components/AlertBadge'
import LiveIndicator from '../components/LiveIndicator'
import { getTrainCurrent, getTrainHistory } from '../api'

function Metric({ label, value, unit, color = 'var(--cyan)', large = false }) {
  return (
    <div style={{ padding: '16px 20px', background: 'var(--glass)', backdropFilter: 'var(--blur-sm)', WebkitBackdropFilter: 'var(--blur-sm)', border: `1px solid ${color}20`, borderRadius: 'var(--r-md)', flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--t3)', textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
      <div className="mono" style={{ fontSize: large ? 28 : 22, fontWeight: 800, color, lineHeight: 1 }}>
        {value ?? '—'}{unit && <span style={{ fontSize: large ? 14 : 12, fontWeight: 500, marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  )
}

export default function TrainDetail() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const [train,    setTrain]   = useState(null)
  const [history,  setHistory] = useState([])
  const [loading,  setLoading] = useState(true)
  const [live,     setLive]    = useState(false)

  const load = async () => {
    try {
      const [train, hist] = await Promise.all([
        getTrainCurrent(id),
        getTrainHistory(id, 12),
      ])
      if (train) { setTrain(train); setLive(true) }
      if (hist.length) {
        const chartData = hist.slice(-60).map(d => ({
          time:   new Date(d.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
          speed:  d.speed  || 0,
          stress: d.stress_score ? +(d.stress_score * 100).toFixed(1) : 0,
          delay:  d.delay_minutes || 0,
        }))
        setHistory(chartData)
      }
    } catch { setLive(false) }
    setLoading(false)
  }
  useEffect(() => { load(); const iv = setInterval(load, 12000); return () => clearInterval(iv) }, [id])

  const stressColor = {
    CRITICAL: 'var(--red)', HIGH: 'var(--orange)',
    MEDIUM: 'var(--yellow)', LOW: 'var(--green)', STABLE: 'var(--cyan)',
  }[train?.stress_level] || 'var(--cyan)'

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--t3)' }}>
      Loading train data...
    </div>
  )

  if (!train) return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>⟁</div>
      <div style={{ fontSize: 16, color: 'var(--t2)', marginBottom: 8 }}>Train {id} not found</div>
      <button onClick={() => navigate('/trains')} style={{ padding: '8px 20px', background: 'var(--cyan-10)', border: '1px solid var(--cyan-30)', borderRadius: 'var(--r-sm)', color: 'var(--cyan)', cursor: 'pointer', fontSize: 13 }}>
        ← Back to Trains
      </button>
    </div>
  )

  return (
    <div style={{ padding: '32px 28px', maxWidth: 1200, margin: '0 auto' }}>
      {/* Back */}
      <button onClick={() => navigate('/trains')} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 20, background: 'none', border: 'none', color: 'var(--t2)', fontSize: 13, cursor: 'pointer', padding: 0 }}>
        ← Back to Trains
      </button>

      {/* Hero */}
      <div style={{ padding: '24px 28px', background: `linear-gradient(135deg, ${stressColor}10, var(--surface))`, border: `1px solid ${stressColor}30`, borderRadius: 'var(--r-lg)', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 8 }}>
              <h1 className="mono" style={{ fontSize: 32, fontWeight: 900, color: stressColor, letterSpacing: '0.1em' }}>
                {train.train_id}
              </h1>
              <AlertBadge severity={train.stress_level} size="lg" />
              <LiveIndicator offline={!live} />
            </div>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13, color: 'var(--t2)' }}>
              {train.zone && <span>◉ Zone: <strong style={{ color: 'var(--t1)' }}>{train.zone}</strong></span>}
              {train.current_station && <span>📍 At: <strong style={{ color: 'var(--t1)' }}>{train.current_station}</strong></span>}
              {train.next_station    && <span>→ Next: <strong style={{ color: 'var(--t1)' }}>{train.next_station}</strong></span>}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: 'var(--t3)', marginBottom: 4 }}>Last updated</div>
            <div className="mono" style={{ fontSize: 13, color: 'var(--t2)' }}>
              {train.timestamp ? new Date(train.timestamp).toLocaleTimeString('en-IN') : '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <Metric label="Speed"      value={train.speed != null ? Math.round(train.speed) : null} unit="km/h" color="var(--cyan)" large />
        <Metric label="Stress Score" value={train.stress_score != null ? (train.stress_score * 100).toFixed(1) : null} unit="%" color={stressColor} large />
        <Metric label="Delay"      value={train.delay_minutes} unit="min" color={train.delay_minutes > 0 ? 'var(--orange)' : 'var(--green)'} large />
        {train.occupancy    != null && <Metric label="Occupancy"     value={Math.round(train.occupancy * 100)} unit="%" color="var(--purple)" />}
        {train.track_quality!= null && <Metric label="Track Quality" value={(train.track_quality * 100).toFixed(0)} unit="%" color="var(--green)" />}
        {train.weather      != null && <Metric label="Wx Factor"     value={(train.weather * 100).toFixed(0)} unit="%" color="var(--yellow)" />}
      </div>

      {/* Charts */}
      {history.length > 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
          {/* Speed chart */}
          <div style={{ padding: '20px', background: 'var(--glass)', backdropFilter: 'var(--blur)', WebkitBackdropFilter: 'var(--blur)', border: '1px solid var(--b1)', borderRadius: 'var(--r-md)' }}>
            <div style={{ marginBottom: 12, fontSize: 12, fontWeight: 700, color: 'var(--t2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Speed History — 12h</div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="speedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--cyan)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--cyan)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--b1)" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: 'var(--t3)', fontSize: 9 }} tickLine={false} axisLine={false} interval={Math.floor(history.length / 6)} />
                <YAxis tick={{ fill: 'var(--t3)', fontSize: 9 }} tickLine={false} axisLine={false} unit=" km/h" width={55} />
                <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--b2)', borderRadius: 8, fontSize: 11 }} itemStyle={{ color: 'var(--cyan)' }} labelStyle={{ color: 'var(--t2)' }} />
                <Area type="monotone" dataKey="speed" name="Speed" stroke="var(--cyan)" strokeWidth={2} fill="url(#speedGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Stress chart */}
          <div style={{ padding: '20px', background: 'var(--glass)', backdropFilter: 'var(--blur)', WebkitBackdropFilter: 'var(--blur)', border: '1px solid var(--b1)', borderRadius: 'var(--r-md)' }}>
            <div style={{ marginBottom: 12, fontSize: 12, fontWeight: 700, color: 'var(--t2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Stress Score — 12h</div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="stressGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--orange)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--orange)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--b1)" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: 'var(--t3)', fontSize: 9 }} tickLine={false} axisLine={false} interval={Math.floor(history.length / 6)} />
                <YAxis tick={{ fill: 'var(--t3)', fontSize: 9 }} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" width={40} />
                <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--b2)', borderRadius: 8, fontSize: 11 }} itemStyle={{ color: 'var(--orange)' }} labelStyle={{ color: 'var(--t2)' }} />
                <Area type="monotone" dataKey="stress" name="Stress" stroke="var(--orange)" strokeWidth={2} fill="url(#stressGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Raw data */}
      <div style={{ padding: '20px', background: 'var(--glass)', backdropFilter: 'var(--blur)', WebkitBackdropFilter: 'var(--blur)', border: '1px solid var(--b1)', borderRadius: 'var(--r-md)' }}>
        <div style={{ marginBottom: 12, fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t3)', textTransform: 'uppercase' }}>Full Telemetry Snapshot</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
          {Object.entries(train).filter(([k]) => k !== 'train_id').map(([key, val]) => (
            <div key={key} style={{ padding: '8px 12px', background: 'var(--surface)', borderRadius: 'var(--r-sm)', border: '1px solid var(--b1)' }}>
              <div style={{ fontSize: 9, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 3 }}>{key.replace(/_/g, ' ')}</div>
              <div className="mono" style={{ fontSize: 12, color: 'var(--t1)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {val === null ? '—' : typeof val === 'number' ? val.toFixed ? val.toFixed(3) : val : String(val)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
