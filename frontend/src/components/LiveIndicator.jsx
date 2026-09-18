/**
 * LiveIndicator — connection status pill
 */
export default function LiveIndicator({ label, offline, color }) {
  const mode = offline ? 'offline' : 'online'
  return (
    <div className={`live-pill ${mode}`} style={color && !offline ? { color, borderColor: color, background: `${color}12` } : {}}>
      <span
        className="pulse-dot"
        style={{
          background: offline ? 'var(--t4)' : (color || 'var(--green)'),
          animation: offline ? 'none' : 'pulse-dot 2s ease-in-out infinite',
        }}
      />
      {label || (offline ? 'OFFLINE' : 'LIVE')}
    </div>
  )
}
