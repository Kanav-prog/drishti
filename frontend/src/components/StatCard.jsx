/**
 * StatCard — unified KPI display card
 */
export default function StatCard({ label, value, color, sub, icon }) {
  return (
    <div className="stat-card">
      <div className="stat-card-accent" style={{ background: color || 'var(--border)' }} />
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value" style={{ color: color || 'var(--t1)' }}>
        {icon && <span style={{ marginRight: 4, fontSize: 18 }}>{icon}</span>}
        {value ?? '—'}
      </div>
      {sub && <div className="stat-card-sub">{sub}</div>}
    </div>
  )
}
