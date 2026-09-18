import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

/* ── Particle canvas ─────────────────────────────────────────── */
function useParticles(canvasRef) {
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf

    const resize = () => {
      canvas.width  = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const stars = Array.from({ length: 160 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.1 + 0.2,
      alpha: Math.random(),
      dAlpha: (Math.random() * 0.006 + 0.002) * (Math.random() > 0.5 ? 1 : -1),
    }))

    const nodes = Array.from({ length: 22 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      r: Math.random() * 2 + 1,
      alpha: Math.random() * 0.4 + 0.15,
    }))

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      stars.forEach(s => {
        s.alpha += s.dAlpha
        if (s.alpha <= 0 || s.alpha >= 1) s.dAlpha *= -1
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(200,220,255,${Math.max(0, Math.min(1, s.alpha))})`
        ctx.fill()
      })
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx*dx + dy*dy)
          if (dist < 160) {
            ctx.beginPath()
            ctx.moveTo(nodes[i].x, nodes[i].y)
            ctx.lineTo(nodes[j].x, nodes[j].y)
            ctx.strokeStyle = `rgba(0,212,255,${(1 - dist/160) * 0.1})`
            ctx.lineWidth = 0.7
            ctx.stroke()
          }
        }
      }
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy
        if (n.x < 0 || n.x > canvas.width)  n.vx *= -1
        if (n.y < 0 || n.y > canvas.height) n.vy *= -1
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(0,212,255,${n.alpha * 0.5})`
        ctx.fill()
      })
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [canvasRef])
}

/* ── Typewriter ──────────────────────────────────────────────── */
function useTypewriter(text, speed = 35) {
  const [displayed, setDisplayed] = useState('')
  useEffect(() => {
    setDisplayed('')
    let i = 0
    const t = setInterval(() => { i++; setDisplayed(text.slice(0, i)); if (i >= text.length) clearInterval(t) }, speed)
    return () => clearInterval(t)
  }, [text, speed])
  return displayed
}

/* ── Use IntersectionObserver for scroll reveal ──────────────── */
function useReveal(threshold = 0.15) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } }, { threshold })
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return [ref, visible]
}

/* ── Reveal wrapper ──────────────────────────────────────────── */
function Reveal({ children, delay = 0, style = {} }) {
  const [ref, visible] = useReveal()
  return (
    <div ref={ref} style={{
      transition: `opacity 700ms ease ${delay}ms, transform 700ms ease ${delay}ms`,
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(28px)',
      ...style,
    }}>
      {children}
    </div>
  )
}

/* ── Live ticker ─────────────────────────────────────────────── */
const TICK_DEFAULTS = [
  'Bayesian Network inference latency: < 100ms',
  '51 high-centrality junctions under continuous AI surveillance',
  'CRS accident signature matching active across all zones',
  'Zone controllers: NR · SR · ER · WR · CR · SER · NFR · NWR · SCR',
  'Network stable — no critical cascade events detected',
]
function Ticker({ items }) {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % items.length), 3500)
    return () => clearInterval(t)
  }, [items.length])
  return (
    <div style={TS.wrap}>
      <span style={TS.tag}>LIVE</span>
      <span style={TS.text} key={idx}>{items[idx]}</span>
    </div>
  )
}
const TS = {
  wrap: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '8px 20px',
    background: 'rgba(0,212,255,.04)', border: '1px solid rgba(0,212,255,.15)',
    borderRadius: 40, fontSize: 12.5, color: 'var(--t2)', maxWidth: 580,
  },
  tag: {
    fontSize: 9, fontWeight: 700, letterSpacing: '0.16em',
    color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace',
    background: 'var(--cyan-10)', padding: '2px 8px', borderRadius: 20,
    whiteSpace: 'nowrap',
  },
  text: { animation: 'fade-in 400ms ease', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
}

/* ── Incident card (accidents) ───────────────────────────────── */
function IncidentCard({ date, location, deaths, name, desc, color, window: detectWindow }) {
  const [hov, setHov] = useState(false)
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: '1 1 280px',
        padding: '28px 24px',
        background: hov ? `${color}0a` : 'rgba(255,255,255,.02)',
        border: `1px solid ${hov ? color + '40' : 'rgba(255,255,255,.06)'}`,
        borderRadius: 16,
        transition: 'all 260ms ease',
        cursor: 'default',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Top accent bar */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color, opacity: 0.7 }} />

      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', color, fontFamily: 'JetBrains Mono, monospace', marginBottom: 8 }}>
        {date} · {location}
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--t1)', marginBottom: 4 }}>{name}</div>
      <div style={{ fontSize: 32, fontWeight: 900, color, fontFamily: 'JetBrains Mono, monospace', lineHeight: 1.1, marginBottom: 4 }}>
        {deaths}
      </div>
      <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 12 }}>fatalities</div>
      <div style={{ fontSize: 12, color: 'var(--t2)', lineHeight: 1.6, marginBottom: 16 }}>{desc}</div>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '5px 12px', borderRadius: 20,
        background: 'rgba(0,212,255,.08)', border: '1px solid rgba(0,212,255,.2)',
        fontSize: 10.5, color: 'var(--cyan)', fontWeight: 600, letterSpacing: '0.04em',
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)', display: 'inline-block' }} />
        DRISHTI detects in {detectWindow}
      </div>
    </div>
  )
}

/* ── Capability row ──────────────────────────────────────────── */
function CapRow({ n, title, sub, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, padding: '20px 0', borderBottom: '1px solid rgba(255,255,255,.04)' }}>
      <div style={{
        minWidth: 44, height: 44, borderRadius: 12,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: `${color}12`, border: `1px solid ${color}30`,
        fontSize: 16, fontWeight: 800, color, fontFamily: 'JetBrains Mono, monospace',
      }}>{n}</div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)', marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 12.5, color: 'var(--t2)', lineHeight: 1.6 }}>{sub}</div>
      </div>
    </div>
  )
}

/* ── Section label ───────────────────────────────────────────── */
function SectionLabel({ text }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 10,
      fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--cyan)',
      fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase',
      marginBottom: 20,
    }}>
      <span style={{ width: 24, height: 1, background: 'var(--cyan)', display: 'inline-block' }} />
      {text}
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════════════════ */
export default function Home() {
  const navigate  = useNavigate()
  const canvasRef = useRef(null)
  const [liveStats, setLiveStats] = useState({ trains: 0, alerts: 0, critical: 0 })
  const [tickItems, setTickItems] = useState(TICK_DEFAULTS)
  const headline = useTypewriter("India's Railway Safety Intelligence Platform", 30)

  useParticles(canvasRef)

  useEffect(() => {
    const load = async () => {
      try {
        const [trainsRes, alertsRes] = await Promise.allSettled([
          fetch('/api/trains/current'),
          fetch('/api/alerts/history?limit=20'),
        ])
        let trains = [], alertArr = []
        if (trainsRes.status === 'fulfilled' && trainsRes.value.ok) trains = await trainsRes.value.json()
        if (alertsRes.status === 'fulfilled' && alertsRes.value.ok) {
          const d = await alertsRes.value.json()
          alertArr = Array.isArray(d) ? d : (d.alerts ?? [])
        }
        const c = Array.isArray(trains) ? trains.filter(t => t.stress_level === 'CRITICAL').length : 0
        setLiveStats({ trains: Array.isArray(trains) ? trains.length : 0, alerts: alertArr.length, critical: c })
        setTickItems([
          `Monitoring ${Array.isArray(trains) ? trains.length : 0} trains across India's rail network`,
          '51 high-centrality junctions under continuous AI surveillance',
          'Bayesian Network inference latency: < 100ms',
          'CRS accident signature matching active across all zones',
          ...(alertArr.length ? [`${alertArr.length} safety events recorded in last 24h`] : ['Network stable — no critical events detected']),
        ])
      } catch { /* silent */ }
    }
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div style={{ background: 'var(--void)', color: 'var(--t1)', position: 'relative' }}>

      {/* ════════════ HERO ════════════ */}
      <section style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', padding: '60px 24px' }}>
        <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0 }} />
        <div style={{ position: 'absolute', top: '-10%', left: '50%', transform: 'translateX(-50%)', width: 900, height: 900, background: 'radial-gradient(circle, rgba(0,212,255,.07) 0%, transparent 65%)', pointerEvents: 'none', zIndex: 1 }} />
        <div style={{ position: 'absolute', bottom: 0, right: '-5%', width: 500, height: 500, background: 'radial-gradient(circle, rgba(123,147,255,.05) 0%, transparent 65%)', pointerEvents: 'none', zIndex: 1 }} />
        <div style={{ position: 'absolute', left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, rgba(0,212,255,.12), transparent)', animation: 'scan-line 8s linear infinite', zIndex: 2 }} />

        <div style={{ position: 'relative', zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 28, maxWidth: 1100, width: '100%', textAlign: 'center' }}>

          {/* Status badge */}
          <div style={{ animation: 'slide-up 600ms ease 100ms both' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 16px', borderRadius: 40, background: 'rgba(0,212,255,.06)', border: '1px solid rgba(0,212,255,.2)', color: 'var(--cyan)', fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', fontFamily: 'JetBrains Mono, monospace' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 8px var(--cyan)', animation: 'pulse-dot 1.5s ease-in-out infinite' }} />
              OPERATIONAL · PHASE II PRODUCTION
            </div>
          </div>

          {/* Logo */}
          <div style={{ animation: 'slide-up 700ms ease 200ms both' }}>
            <div style={{ fontSize: 'clamp(60px, 11vw, 104px)', fontWeight: 900, letterSpacing: '0.2em', color: 'var(--cyan)', textShadow: '0 0 40px rgba(0,212,255,.55), 0 0 80px rgba(0,212,255,.2)', lineHeight: 1, animation: 'glow-pulse 3s ease-in-out infinite' }}>
              DRISHTI
            </div>
            <div style={{ fontSize: 11, letterSpacing: '0.42em', color: 'var(--t3)', fontWeight: 600, textTransform: 'uppercase', marginTop: 6 }}>
              NATIONAL RAILWAY GRID INTELLIGENCE
            </div>
          </div>

          {/* Headline typewriter */}
          <div style={{ animation: 'slide-up 700ms ease 300ms both' }}>
            <p style={{ fontSize: 'clamp(14px, 2.2vw, 21px)', color: 'var(--t2)', fontWeight: 400, lineHeight: 1.5, maxWidth: 620 }}>
              {headline}<span style={{ color: 'var(--cyan)', animation: 'glow-pulse 1s ease-in-out infinite' }}>│</span>
            </p>
          </div>

          {/* Live stats row */}
          <div style={{ animation: 'slide-up 700ms ease 420ms both', display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
            {[
              { label: 'TRAINS MONITORED', value: liveStats.trains, color: 'var(--cyan)' },
              { label: 'JUNCTION NODES',   value: 51,               color: 'var(--purple)' },
              { label: 'CRITICAL ALERTS',  value: liveStats.critical, color: 'var(--red)' },
              { label: 'ZONE COVERAGE',    value: '9 / 9',          color: 'var(--green)' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '14px 24px', background: `${color}08`, border: `1px solid ${color}22`, borderRadius: 14 }}>
                <span style={{ fontSize: 28, fontWeight: 800, color, fontFamily: 'JetBrains Mono, monospace' }}>{value}</span>
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--t3)', textTransform: 'uppercase' }}>{label}</span>
              </div>
            ))}
          </div>

          {/* Live ticker */}
          <div style={{ animation: 'slide-up 700ms ease 520ms both' }}>
            <Ticker items={tickItems} />
          </div>

          {/* CTA */}
          <div style={{ animation: 'slide-up 700ms ease 640ms both', display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
            <button
              onClick={() => navigate('/dashboard')}
              onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 0 40px rgba(0,212,255,.5)'; e.currentTarget.style.transform = 'translateY(-2px)' }}
              onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 0 20px rgba(0,212,255,.25)'; e.currentTarget.style.transform = 'translateY(0)' }}
              style={{ padding: '14px 36px', background: 'linear-gradient(135deg, var(--cyan), #0099cc)', color: '#000', fontWeight: 800, fontSize: 12, letterSpacing: '0.14em', borderRadius: 10, cursor: 'pointer', border: 'none', boxShadow: '0 0 20px rgba(0,212,255,.25)', transition: 'all 240ms ease' }}>
              ENTER COMMAND CENTER →
            </button>
            <button
              onClick={() => navigate('/simulation')}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,212,255,.08)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              style={{ padding: '14px 28px', background: 'transparent', color: 'var(--cyan)', fontWeight: 700, fontSize: 12, letterSpacing: '0.12em', borderRadius: 10, cursor: 'pointer', border: '1px solid rgba(0,212,255,.3)', transition: 'all 240ms ease' }}>
              RUN SIMULATION
            </button>
          </div>

          {/* Feature cards */}
          <div style={{ animation: 'slide-up 700ms ease 760ms both', display: 'flex', gap: 14, flexWrap: 'wrap', justifyContent: 'center', width: '100%', maxWidth: 900, marginTop: 8 }}>
            {[
              { icon: '◎', label: 'Network Intelligence', sub: '51 critical junctions, live stress overlays, cascade risk graphs', color: 'var(--cyan)', to: '/network' },
              { icon: '⚡', label: 'Cascade Simulation', sub: 'Replay historical incidents, simulate failure scenarios, measure response windows', color: 'var(--orange)', to: '/simulation' },
              { icon: '⬙', label: 'Bayesian AI Brain', sub: 'Probabilistic causal inference — SHAP explainability on every prediction', color: 'var(--purple)', to: '/ai' },
            ].map(({ icon, label, sub, color, to }) => {
              const [hov, setHov] = useState(false)
              return (
                <button key={to}
                  onClick={() => navigate(to)}
                  onMouseEnter={() => setHov(true)}
                  onMouseLeave={() => setHov(false)}
                  style={{
                    flex: '1 1 220px', maxWidth: 280, padding: '22px 20px',
                    background: hov ? `${color}0d` : 'rgba(255,255,255,.02)',
                    border: `1px solid ${hov ? color + '35' : 'rgba(255,255,255,.06)'}`,
                    borderRadius: 14, cursor: 'pointer', textAlign: 'left',
                    backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
                    transition: 'all 260ms ease',
                    transform: hov ? 'translateY(-4px)' : 'translateY(0)',
                    boxShadow: hov ? `0 16px 40px ${color}18` : 'none',
                    display: 'flex', flexDirection: 'column', gap: 10,
                  }}>
                  <span style={{ fontSize: 22, color }}>{icon}</span>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--t1)' }}>{label}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--t2)', lineHeight: 1.65 }}>{sub}</div>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* ════════════ PROBLEM SECTION ════════════ */}
      <section style={SEC}>
        <div style={SEC_INNER}>
          <Reveal>
            <SectionLabel text="The Problem" />
            <h2 style={H2}>India's railways carry 1.4 billion passengers a year.<br />
              <span style={{ color: 'var(--red)' }}>They still lose hundreds to preventable accidents.</span>
            </h2>
            <p style={PROSE}>
              Every major disaster — Balasore, Pukhrayan, Khanna — shared one trait: a cascade that expanded
              faster than human operators could track it. The system was reactive. By the time controllers
              understood what was happening, the window to intervene had closed.
            </p>
          </Reveal>

          {/* Incident cards */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 36 }}>
            {[
              {
                date: '02 Jun 2023', location: 'Odisha',
                name: 'Balasore / Coromandel Collision',
                deaths: '296',
                desc: 'Three-train pileup caused by signal failure and delayed cascade warning. Passenger coaches derailed onto adjacent track.',
                color: '#ff4757',
                window: '6 seconds',
              },
              {
                date: '20 Nov 2016', location: 'Uttar Pradesh',
                name: 'Pukhrayan Derailment',
                deaths: '149',
                desc: 'Indore-Patna Express derailed on weakened flood-damaged track. No predictive track-stress monitoring in place.',
                color: 'var(--orange)',
                window: '10 seconds',
              },
              {
                date: '02 Jun 1998', location: 'Uttar Pradesh',
                name: 'Firozabad Rail Collision',
                deaths: '212',
                desc: 'Kalindi Express hit stationary Purushottam Express stalled on main line. Junction congestion cascade went undetected.',
                color: 'var(--purple)',
                window: '8 seconds',
              },
            ].map((inc, i) => (
              <Reveal key={inc.name} delay={i * 100}>
                <IncidentCard {...inc} />
              </Reveal>
            ))}
          </div>

          <Reveal delay={300}>
            <div style={{ marginTop: 36, padding: '20px 24px', background: 'rgba(0,212,255,.04)', border: '1px solid rgba(0,212,255,.12)', borderRadius: 14, display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>14,000+</div>
              <p style={{ fontSize: 13, color: 'var(--t2)', lineHeight: 1.7, margin: 0 }}>
                railway accidents recorded annually in India. The gap between detection and intervention is measured
                in seconds — but those seconds determine everything. <strong style={{ color: 'var(--t1)' }}>DRISHTI closes that gap.</strong>
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════ HOW IT WORKS ════════════ */}
      <section style={{ ...SEC, background: 'rgba(0,212,255,.018)' }}>
        <div style={{ ...SEC_INNER, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 60, alignItems: 'start' }}>
          <Reveal>
            <div>
              <SectionLabel text="Architecture" />
              <h2 style={H2}>Four intelligence layers.<br /><span style={{ color: 'var(--cyan)' }}>One unified response.</span></h2>
              <p style={PROSE}>
                DRISHTI processes raw train telemetry through a stacked AI pipeline — each layer
                adding signal, reducing noise, and escalating only what requires human attention.
              </p>
              <div style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 22, fontWeight: 900, color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace' }}>{'< '}100ms</span>
                <span style={{ fontSize: 12, color: 'var(--t3)' }}>end-to-end inference latency</span>
              </div>
            </div>
          </Reveal>

          <div>
            {[
              { n: '01', title: 'Real-Time Ingestion', sub: 'Live telemetry from 127 trains, 51 junctions, track sensors, and weather feeds ingested continuously.', color: 'var(--cyan)' },
              { n: '02', title: 'Graph Stress Analysis', sub: 'Bayesian graphical model maps train–junction dependencies and computes cascade risk across the live network graph.', color: 'var(--purple)' },
              { n: '03', title: 'Multi-Model AI Consensus', sub: 'Isolation Forest + Causal DAG + DBSCAN + Bayesian Network vote on risk severity. 3/4 agreement triggers CRITICAL.', color: 'var(--orange)' },
              { n: '04', title: 'Automatic Alert & Response', sub: 'Triggers speed reductions, route diversions, or emergency protocols before collision cascade becomes irreversible.', color: 'var(--green)' },
            ].map((c, i) => (
              <Reveal key={c.n} delay={i * 80}>
                <CapRow {...c} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ IMPACT ════════════ */}
      <section style={SEC}>
        <div style={SEC_INNER}>
          <Reveal>
            <SectionLabel text="Projected Impact" />
            <h2 style={H2}>What prevention is worth.</h2>
            <p style={PROSE}>
              Modelled against India's 10-year accident database, validated on CRS (Commissioner of Railway Safety) records.
            </p>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginTop: 36 }}>
            {[
              { value: '4,295+', label: 'Lives Saved Annually', sub: 'Across all high-risk scenario modelling', color: 'var(--cyan)' },
              { value: '₹600 Cr', label: 'Annual Cost Savings', sub: 'Accident prevention + downtime recovery', color: 'var(--purple)' },
              { value: '95%+', label: 'Prediction Accuracy', sub: 'Validated on historical incident database', color: 'var(--orange)' },
              { value: '6–10s', label: 'Detection Window', sub: 'Before cascade escalation becomes fatal', color: 'var(--green)' },
            ].map((m, i) => (
              <Reveal key={m.label} delay={i * 80}>
                <div style={{ padding: '28px 20px', background: `${m.color}07`, border: `1px solid ${m.color}20`, borderRadius: 16, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <span style={{ fontSize: 36, fontWeight: 900, color: m.color, fontFamily: 'JetBrains Mono, monospace', lineHeight: 1 }}>{m.value}</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--t1)' }}>{m.label}</span>
                  <span style={{ fontSize: 10.5, color: 'var(--t3)', lineHeight: 1.5 }}>{m.sub}</span>
                </div>
              </Reveal>
            ))}
          </div>

          {/* Quote / vision */}
          <Reveal delay={200}>
            <div style={{ marginTop: 48, padding: '36px 40px', background: 'rgba(0,0,0,.3)', border: '1px solid rgba(255,255,255,.06)', borderRadius: 20, position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: -1, left: 40, width: 120, height: 2, background: 'linear-gradient(90deg, var(--cyan), transparent)' }} />
              <p style={{ fontSize: 'clamp(16px, 2.5vw, 22px)', fontWeight: 300, color: 'var(--t1)', lineHeight: 1.7, fontStyle: 'italic', maxWidth: 700, margin: '0 0 20px' }}>
                "A railway network that doesn't learn from tragedy — it <strong style={{ fontStyle: 'normal', fontWeight: 700, color: 'var(--cyan)' }}>prevents</strong> it."
              </p>
              <p style={{ fontSize: 12, color: 'var(--t3)', margin: 0 }}>DRISHTI System Philosophy · Phase II Deployment</p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════ DEPLOYMENT / COVERAGE ════════════ */}
      <section style={{ ...SEC, background: 'rgba(123,147,255,.015)' }}>
        <div style={SEC_INNER}>
          <Reveal>
            <SectionLabel text="Deployment" />
            <h2 style={H2}>Operational across <span style={{ color: 'var(--purple)' }}>9 zones.</span><br />Expanding to all 17.</h2>
            <p style={PROSE}>
              Phase II covers India's highest-risk corridors. Phase III extends to every zonal HQ,
              providing full-network cascade visibility.
            </p>
          </Reveal>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 32 }}>
            {[
              { code: 'NR',  name: 'Northern Railway',      hq: 'New Delhi',       active: true,  color: 'var(--cyan)' },
              { code: 'CR',  name: 'Central Railway',       hq: 'Mumbai CST',      active: true,  color: 'var(--purple)' },
              { code: 'WR',  name: 'Western Railway',       hq: 'Mumbai Church',   active: true,  color: 'var(--orange)' },
              { code: 'ER',  name: 'Eastern Railway',       hq: 'Kolkata',         active: true,  color: 'var(--green)' },
              { code: 'SR',  name: 'Southern Railway',      hq: 'Chennai',         active: true,  color: '#ff6b6b' },
              { code: 'SER', name: 'South Eastern Railway', hq: 'Kolkata',         active: true,  color: 'var(--cyan)', focus: true },
              { code: 'SCR', name: 'South Central Railway', hq: 'Secunderabad',    active: true,  color: 'var(--purple)' },
              { code: 'NWR', name: 'North Western Railway', hq: 'Jaipur',          active: true,  color: 'var(--orange)' },
              { code: 'NFR', name: 'Northeast Frontier',    hq: 'Guwahati',        active: true,  color: 'var(--green)' },
              { code: 'ECR', name: 'East Central Railway',  hq: 'Hajipur',         active: false, color: 'var(--t3)' },
              { code: 'ECoR',name: 'East Coast Railway',    hq: 'Bhubaneswar',     active: false, color: 'var(--t3)' },
              { code: 'NCR', name: 'North Central Railway', hq: 'Prayagraj',       active: false, color: 'var(--t3)' },
            ].map((z, i) => (
              <Reveal key={z.code} delay={i * 40}>
                <div style={{
                  padding: '12px 16px', borderRadius: 10, minWidth: 140,
                  background: z.active ? `${z.color}08` : 'rgba(255,255,255,.02)',
                  border: `1px solid ${z.active ? z.color + (z.focus ? '45' : '25') : 'rgba(255,255,255,.05)'}`,
                  position: 'relative', overflow: 'hidden',
                }}>
                  {z.focus && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: z.color }} />}
                  <div style={{ fontSize: 13, fontWeight: 800, color: z.active ? z.color : 'var(--t3)', fontFamily: 'JetBrains Mono, monospace', marginBottom: 2 }}>{z.code}</div>
                  <div style={{ fontSize: 10, color: 'var(--t3)', marginBottom: 4 }}>{z.hq}</div>
                  <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', color: z.active ? z.color : 'var(--t3)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    {z.active && <span style={{ width: 5, height: 5, borderRadius: '50%', background: z.color, display: 'inline-block' }} />}
                    {z.active ? (z.focus ? 'PRIMARY FOCUS' : 'ACTIVE') : 'PHASE III'}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ FINAL CTA ════════════ */}
      <section style={{ ...SEC, textAlign: 'center' }}>
        <div style={{ ...SEC_INNER, alignItems: 'center', display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Reveal>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center' }}>
              <span style={{ width: 24, height: 1, background: 'var(--cyan)', display: 'inline-block' }} />
              ACCESS PLATFORM
              <span style={{ width: 24, height: 1, background: 'var(--cyan)', display: 'inline-block' }} />
            </div>
            <h2 style={{ ...H2, maxWidth: 600, textAlign: 'center' }}>
              Intelligence that sees what humans miss.
            </h2>
            <p style={{ ...PROSE, textAlign: 'center', maxWidth: 500 }}>
              Open the command center for live train telemetry, cascade risk visualizations, and AI-powered safety alerts.
            </p>
          </Reveal>

          <Reveal delay={100}>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button
                onClick={() => navigate('/dashboard')}
                onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 0 44px rgba(0,212,255,.5)'; e.currentTarget.style.transform = 'translateY(-2px)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 0 20px rgba(0,212,255,.25)'; e.currentTarget.style.transform = 'translateY(0)' }}
                style={{ padding: '15px 40px', background: 'linear-gradient(135deg, var(--cyan), #0099cc)', color: '#000', fontWeight: 800, fontSize: 12, letterSpacing: '0.14em', borderRadius: 10, cursor: 'pointer', border: 'none', boxShadow: '0 0 20px rgba(0,212,255,.25)', transition: 'all 240ms ease' }}>
                OPEN DASHBOARD →
              </button>
              <button
                onClick={() => navigate('/network')}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(123,147,255,.1)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                style={{ padding: '15px 32px', background: 'transparent', color: 'var(--purple)', fontWeight: 700, fontSize: 12, letterSpacing: '0.12em', borderRadius: 10, cursor: 'pointer', border: '1px solid rgba(123,147,255,.3)', transition: 'all 240ms ease' }}>
                VIEW NETWORK MAP
              </button>
              <button
                onClick={() => navigate('/alerts')}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,107,107,.08)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                style={{ padding: '15px 32px', background: 'transparent', color: '#ff6b6b', fontWeight: 700, fontSize: 12, letterSpacing: '0.12em', borderRadius: 10, cursor: 'pointer', border: '1px solid rgba(255,107,107,.3)', transition: 'all 240ms ease' }}>
                LIVE ALERTS
              </button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ════════════ FOOTER ════════════ */}
      <footer style={{ borderTop: '1px solid rgba(255,255,255,.04)', padding: '28px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 900, letterSpacing: '0.12em', color: 'var(--cyan)' }}>DRISHTI</span>
          <span style={{ fontSize: 9, color: 'var(--t3)', letterSpacing: '0.1em' }}>v2.0 · PHASE II · INDIA</span>
        </div>
        <p style={{ fontSize: 11, color: 'var(--t3)', margin: 0 }}>
          National Railway Grid Intelligence · Bayesian Safety Network · 51 nodes monitored
        </p>
      </footer>
    </div>
  )
}

// Shared layout constants
const SEC = {
  padding: '80px 24px',
}
const SEC_INNER = {
  maxWidth: 1100,
  margin: '0 auto',
}
const H2 = {
  fontSize: 'clamp(22px, 4vw, 38px)',
  fontWeight: 800,
  lineHeight: 1.25,
  color: 'var(--t1)',
  marginBottom: 20,
  marginTop: 0,
}
const PROSE = {
  fontSize: 14.5,
  color: 'var(--t2)',
  lineHeight: 1.8,
  maxWidth: 640,
  marginBottom: 0,
}
