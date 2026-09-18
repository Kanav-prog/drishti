/**
 * AlertBadge — severity badge using design system classes
 */
export default function AlertBadge({ severity, size }) {
  const sev = (severity || 'LOW').toUpperCase()
  return (
    <span className={`badge badge-${sev.toLowerCase()}`} style={size === 'sm' ? { fontSize: 9.5 } : {}}>
      {sev}
    </span>
  )
}
