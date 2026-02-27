const colors = {
  completed: 'bg-success/20 text-success',
  failed: 'bg-danger/20 text-danger',
  transferred: 'bg-warning/20 text-warning',
  inbound: 'bg-accent/20 text-accent',
  outbound: 'bg-purple-500/20 text-purple-400',
  indexed: 'bg-success/20 text-success',
  pending: 'bg-warning/20 text-warning',
  admin: 'bg-accent/20 text-accent',
  client: 'bg-bg-hover text-text-secondary',
  // Phase 3
  confirmed: 'bg-success/20 text-success',
  cancelled: 'bg-danger/20 text-danger',
  no_show: 'bg-warning/20 text-warning',
  draft: 'bg-bg-hover text-text-secondary',
  scheduled: 'bg-accent/20 text-accent',
  running: 'bg-success/20 text-success',
  paused: 'bg-warning/20 text-warning',
}

export function Badge({ children, variant = 'default', className = '' }) {
  const color = colors[variant] || 'bg-bg-hover text-text-secondary'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${color} ${className}`}>
      {children}
    </span>
  )
}
