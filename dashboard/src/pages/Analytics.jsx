import { useEffect, useState } from 'react'
import {
  BarChart3, Phone, Clock, TrendingUp, Users, Zap, PhoneIncoming,
  PhoneOutgoing, CheckCircle, XCircle, PhoneForwarded, DollarSign,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { UsageChart } from '../components/UsageChart'

const PERIOD_OPTIONS = [
  { value: 7, label: '7 días' },
  { value: 30, label: '30 días' },
  { value: 90, label: '90 días' },
  { value: 365, label: '1 año' },
]

function StatCard({ icon: Icon, label, value, sub, color = 'text-accent' }) {
  return (
    <Card className="flex items-center gap-3">
      <div className={`p-2.5 rounded-lg bg-bg-hover`}>
        <Icon size={20} className={color} />
      </div>
      <div>
        <div className="text-xs text-text-muted">{label}</div>
        <div className={`text-xl font-bold ${color}`}>{value}</div>
        {sub && <div className="text-xs text-text-muted">{sub}</div>}
      </div>
    </Card>
  )
}

function HourChart({ data }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map(d => d.calls), 1)

  return (
    <div className="flex items-end gap-0.5 h-32">
      {data.map(d => (
        <div key={d.hour} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full bg-accent/60 rounded-t hover:bg-accent transition-colors"
            style={{ height: `${(d.calls / max) * 100}%`, minHeight: d.calls > 0 ? 4 : 0 }}
            title={`${d.hour}:00 — ${d.calls} llamadas`}
          />
          {d.hour % 3 === 0 && (
            <span className="text-[9px] text-text-muted">{d.hour}h</span>
          )}
        </div>
      ))}
    </div>
  )
}

function DurationChart({ data }) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map(d => d.count), 1)

  return (
    <div className="space-y-2">
      {data.map(d => (
        <div key={d.range} className="flex items-center gap-3">
          <span className="text-xs text-text-muted w-14 text-right shrink-0">{d.range}</span>
          <div className="flex-1 bg-bg-hover rounded-full h-5 overflow-hidden">
            <div
              className="bg-accent/70 h-full rounded-full transition-all"
              style={{ width: `${(d.count / max) * 100}%` }}
            />
          </div>
          <span className="text-xs font-mono text-text-secondary w-8">{d.count}</span>
        </div>
      ))}
    </div>
  )
}

function StatusDonut({ data }) {
  if (!data || data.length === 0) return null
  const total = data.reduce((s, d) => s + d.count, 0)

  const colors = {
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    transferred: 'bg-yellow-500',
    no_answer: 'bg-gray-500',
    busy: 'bg-orange-500',
  }
  const labels = {
    completed: 'Completada',
    failed: 'Fallida',
    transferred: 'Transferida',
    no_answer: 'Sin respuesta',
    busy: 'Ocupado',
  }

  return (
    <div className="space-y-2">
      {data.map(d => (
        <div key={d.status} className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full shrink-0 ${colors[d.status] || 'bg-gray-400'}`} />
          <span className="text-sm flex-1">{labels[d.status] || d.status}</span>
          <span className="text-sm font-mono text-text-secondary">{d.count}</span>
          <span className="text-xs text-text-muted w-12 text-right">
            {total > 0 ? `${Math.round(d.count / total * 100)}%` : '0%'}
          </span>
        </div>
      ))}
    </div>
  )
}

function AgentTable({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="py-2 px-3 text-xs text-text-muted font-medium">Agente</th>
            <th className="py-2 px-3 text-xs text-text-muted font-medium text-right">Llamadas</th>
            <th className="py-2 px-3 text-xs text-text-muted font-medium text-right">Minutos</th>
            <th className="py-2 px-3 text-xs text-text-muted font-medium text-right">Completadas</th>
            <th className="py-2 px-3 text-xs text-text-muted font-medium text-right">Costo</th>
          </tr>
        </thead>
        <tbody>
          {data.map(a => (
            <tr key={a.agent_id} className="border-b border-border/50 hover:bg-bg-hover transition-colors">
              <td className="py-2 px-3 font-medium">{a.name}</td>
              <td className="py-2 px-3 text-right font-mono">{a.calls}</td>
              <td className="py-2 px-3 text-right font-mono">{a.minutes}</td>
              <td className="py-2 px-3 text-right">
                <span className="text-green-400 font-mono">{a.completion_rate}%</span>
              </td>
              <td className="py-2 px-3 text-right font-mono text-text-muted">${a.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Analytics() {
  const toast = useToast()
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [clientId, setClientId] = useState(null)

  const [summary, setSummary] = useState(null)
  const [volume, setVolume] = useState([])
  const [byStatus, setByStatus] = useState([])
  const [byHour, setByHour] = useState([])
  const [byAgent, setByAgent] = useState([])
  const [durationDist, setDurationDist] = useState([])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const cq = clientId ? `&client_id=${clientId}` : ''
    Promise.all([
      api.get(`/analytics/summary?days=${days}${cq}`),
      api.get(`/analytics/volume?days=${days}${cq}`),
      api.get(`/analytics/by-status?days=${days}${cq}`),
      api.get(`/analytics/by-hour?days=${days}${cq}`),
      api.get(`/analytics/by-agent?days=${days}${cq}`),
      api.get(`/analytics/duration-distribution?days=${days}${cq}`),
    ]).then(([sum, vol, st, hr, ag, dur]) => {
      if (cancelled) return
      setSummary(sum)
      setVolume(vol)
      setByStatus(st)
      setByHour(hr)
      setByAgent(ag)
      setDurationDist(dur)
    }).catch(err => {
      if (!cancelled) toast.error(err.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [days, clientId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <PageLoader />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 size={24} /> Analytics
        </h1>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-border overflow-hidden">
            {PERIOD_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setDays(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium cursor-pointer transition-colors ${
                  days === opt.value
                    ? 'bg-accent text-bg-primary'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <ClientSelector value={clientId} onChange={setClientId} />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard icon={Phone} label="Total llamadas" value={summary?.total_calls || 0} />
        <StatCard icon={Clock} label="Minutos totales" value={summary?.total_minutes || 0} color="text-blue-400" />
        <StatCard icon={TrendingUp} label="Promedio/día" value={summary?.avg_calls_per_day || 0} color="text-green-400" />
        <StatCard icon={Users} label="Callers únicos" value={summary?.unique_callers || 0} color="text-purple-400" />
        <StatCard icon={CheckCircle} label="Tasa completadas" value={`${summary?.completion_rate || 0}%`} color="text-emerald-400" />
        <StatCard icon={DollarSign} label="Costo total" value={`$${summary?.total_cost || 0}`} color="text-yellow-400" />
      </div>

      {/* Direction breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard icon={PhoneIncoming} label="Entrantes" value={summary?.inbound || 0} color="text-cyan-400" />
        <StatCard icon={PhoneOutgoing} label="Salientes" value={summary?.outbound || 0} color="text-orange-400" />
        <StatCard
          icon={Zap}
          label="Duración promedio"
          value={`${Math.round((summary?.avg_duration_seconds || 0) / 60)}m ${Math.round((summary?.avg_duration_seconds || 0) % 60)}s`}
          sub={summary?.busiest_hour != null ? `Hora pico: ${summary.busiest_hour}:00` : undefined}
          color="text-text-primary"
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Volumen diario</h3>
          <UsageChart data={volume} dataKey="calls" label="Llamadas" />
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Por hora del día</h3>
          <HourChart data={byHour} />
        </Card>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Por estado</h3>
          <StatusDonut data={byStatus} />
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Duración de llamadas</h3>
          <DurationChart data={durationDist} />
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Resumen rápido</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-text-muted">Completadas</span>
              <span className="font-mono text-green-400">{summary?.completed || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Fallidas</span>
              <span className="font-mono text-red-400">{summary?.failed || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Transferidas</span>
              <span className="font-mono text-yellow-400">{summary?.transferred || 0}</span>
            </div>
            <hr className="border-border" />
            <div className="flex justify-between">
              <span className="text-text-muted">Período</span>
              <span className="font-mono">{days} días</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Agent performance */}
      {byAgent.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4">Rendimiento por agente</h3>
          <AgentTable data={byAgent} />
        </Card>
      )}
    </div>
  )
}
