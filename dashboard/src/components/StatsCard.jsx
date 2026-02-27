import { Card } from './ui/Card'

export function StatsCard({ icon: Icon, label, value, sub }) {
  return (
    <Card className="flex items-start gap-4">
      <div className="p-2.5 rounded-lg bg-accent/10">
        <Icon size={20} className="text-accent" />
      </div>
      <div>
        <p className="text-text-muted text-xs uppercase tracking-wider">{label}</p>
        <p className="text-2xl font-bold font-mono mt-0.5">{value}</p>
        {sub && <p className="text-text-secondary text-xs mt-0.5">{sub}</p>}
      </div>
    </Card>
  )
}
