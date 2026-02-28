import { Phone, Calendar, Megaphone, Clock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Badge } from './ui/Badge'

const SENTIMIENTO_COLORS = {
  positivo: 'bg-green-500/20 text-green-400',
  neutral: 'bg-yellow-500/20 text-yellow-400',
  negativo: 'bg-red-500/20 text-red-400',
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-MX', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(seconds) {
  if (!seconds) return '0:00'
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function ContactTimeline({ calls = [], appointments = [], campaignCalls = [] }) {
  const navigate = useNavigate()

  // Merge all events into a single chronological list (descending)
  const events = []

  for (const call of calls) {
    events.push({
      type: 'call',
      date: call.started_at,
      data: call,
    })
  }

  for (const apt of appointments) {
    events.push({
      type: 'appointment',
      date: apt.start_time || apt.created_at,
      data: apt,
    })
  }

  for (const cc of campaignCalls) {
    events.push({
      type: 'campaign',
      date: cc.created_at,
      data: cc,
    })
  }

  events.sort((a, b) => new Date(b.date) - new Date(a.date))

  if (events.length === 0) {
    return <p className="text-text-muted text-center py-8">Sin actividad registrada</p>
  }

  return (
    <div className="space-y-3">
      {events.map((event, i) => (
        <TimelineEvent key={`${event.type}-${i}`} event={event} navigate={navigate} />
      ))}
    </div>
  )
}

function TimelineEvent({ event, navigate }) {
  const { type, date, data } = event

  const iconMap = {
    call: Phone,
    appointment: Calendar,
    campaign: Megaphone,
  }
  const Icon = iconMap[type] || Phone

  const colorMap = {
    call: 'text-accent',
    appointment: 'text-green-400',
    campaign: 'text-purple-400',
  }

  return (
    <div
      className={`flex gap-3 p-3 rounded-lg border border-border hover:bg-bg-hover/50 transition-colors ${
        type === 'call' ? 'cursor-pointer' : ''
      }`}
      onClick={() => {
        if (type === 'call' && data.id) navigate(`/calls/${data.id}`)
      }}
    >
      {/* Icon */}
      <div className={`mt-0.5 ${colorMap[type]}`}>
        <Icon size={18} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">
            {type === 'call' && `Llamada ${data.direction === 'inbound' ? 'entrante' : 'saliente'}`}
            {type === 'appointment' && (data.title || 'Cita')}
            {type === 'campaign' && `Campaña: ${data.campaign_name || 'Sin nombre'}`}
          </span>

          {/* Badges */}
          {type === 'call' && data.sentimiento && (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SENTIMIENTO_COLORS[data.sentimiento] || ''}`}>
              {data.sentimiento}
            </span>
          )}
          {type === 'call' && <Badge variant={data.status}>{data.status}</Badge>}
          {type === 'appointment' && <Badge variant={data.status}>{data.status}</Badge>}
          {type === 'campaign' && <Badge variant={data.status}>{data.status}</Badge>}
        </div>

        {/* Detail line */}
        <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
          <span className="flex items-center gap-1">
            <Clock size={11} /> {formatDate(date)}
          </span>
          {type === 'call' && data.duration_seconds > 0 && (
            <span>{formatDuration(data.duration_seconds)}</span>
          )}
          {type === 'call' && data.lead_score != null && data.lead_score > 0 && (
            <span className="text-purple-400">Lead: {data.lead_score}</span>
          )}
        </div>

        {/* Summary */}
        {type === 'call' && data.resumen_ia && (
          <p className="text-xs text-text-secondary mt-1 line-clamp-2">{data.resumen_ia}</p>
        )}
        {type === 'campaign' && data.result_summary && (
          <p className="text-xs text-text-secondary mt-1 line-clamp-2">{data.result_summary}</p>
        )}
        {type === 'appointment' && data.description && (
          <p className="text-xs text-text-secondary mt-1 line-clamp-2">{data.description}</p>
        )}
      </div>
    </div>
  )
}
