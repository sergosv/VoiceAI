import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, Brain, AlertCircle, Target, TrendingUp, Zap, ArrowRightLeft, Star, Activity, Headphones, Mic, Clock, PhoneOff, PhoneIncoming, PhoneOutgoing, User, Bot, Timer } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { TranscriptViewer } from '../components/TranscriptViewer'
import { AudioPlayer } from '../components/AudioPlayer'
import { PageLoader } from '../components/ui/Spinner'

const SENTIMIENTO_COLORS = {
  positivo: 'bg-green-500/20 text-green-400',
  neutral: 'bg-yellow-500/20 text-yellow-400',
  negativo: 'bg-red-500/20 text-red-400',
}

const INTENCION_LABELS = {
  agendar_cita: 'Agendar cita',
  consulta_info: 'Consulta info',
  queja: 'Queja',
  cancelar: 'Cancelar',
  cotizacion: 'Cotización',
  seguimiento: 'Seguimiento',
  otro: 'Otro',
}

const ACCION_LABELS = {
  seguimiento: 'Seguimiento',
  enviar_info: 'Enviar info',
  agendar_cita: 'Agendar cita',
  ninguna: 'Ninguna',
}

const SENTIMENT_RT_COLORS = {
  happy: 'bg-green-400',
  positive: 'bg-green-400',
  neutral: 'bg-gray-400',
  negative: 'bg-orange-400',
  frustrated: 'bg-red-400',
  angry: 'bg-red-400',
}

const SENTIMENT_RT_TEXT = {
  happy: 'text-green-400',
  positive: 'text-green-400',
  neutral: 'text-gray-400',
  negative: 'text-orange-400',
  frustrated: 'text-red-400',
  angry: 'text-red-400',
}

const DISPOSITION_CONFIG = {
  completed: { label: 'Completada', color: 'bg-green-500/20 text-green-400', icon: Phone },
  short_call: { label: 'Llamada corta', color: 'bg-yellow-500/20 text-yellow-400', icon: Timer },
  abandoned: { label: 'Abandonada', color: 'bg-orange-500/20 text-orange-400', icon: PhoneOff },
  no_answer: { label: 'Sin respuesta', color: 'bg-red-500/20 text-red-400', icon: PhoneOff },
  transferred: { label: 'Transferida', color: 'bg-blue-500/20 text-blue-400', icon: ArrowRightLeft },
  voicemail: { label: 'Buzon de voz', color: 'bg-purple-500/20 text-purple-400', icon: Mic },
  error: { label: 'Error', color: 'bg-red-500/20 text-red-400', icon: AlertCircle },
}

const DISCONNECT_LABELS = {
  caller_hangup: 'El usuario colgo',
  agent_hangup: 'El agente termino',
  transfer: 'Transferida',
  no_answer: 'Sin respuesta',
  busy: 'Ocupado',
  timeout_inactivity: 'Timeout por inactividad',
  timeout_max_duration: 'Duracion maxima',
  error_sip: 'Error SIP',
  error_media: 'Error de audio',
  error_agent: 'Error del agente',
  rejected: 'Rechazada',
  voicemail: 'Buzon de voz',
}

const DISCONNECT_BY_ICONS = {
  caller: User,
  agent: Bot,
  system: AlertCircle,
  transfer: ArrowRightLeft,
}

const EVENT_CONFIG = {
  call_initiated: { label: 'Llamada iniciada', color: 'bg-blue-400' },
  sip_answered: { label: 'Contestada', color: 'bg-green-400' },
  agent_ready: { label: 'Agente listo', color: 'bg-accent' },
  first_speech_agent: { label: 'Agente habla', color: 'bg-accent' },
  first_speech_user: { label: 'Usuario habla', color: 'bg-purple-400' },
  user_hangup: { label: 'Usuario colgo', color: 'bg-red-400' },
  agent_hangup: { label: 'Agente termino', color: 'bg-orange-400' },
  transfer_started: { label: 'Transferencia', color: 'bg-blue-400' },
  transfer_completed: { label: 'Transfer OK', color: 'bg-green-400' },
  no_answer: { label: 'Sin respuesta', color: 'bg-red-400' },
  timeout_inactivity: { label: 'Timeout', color: 'bg-yellow-400' },
  error: { label: 'Error', color: 'bg-red-500' },
  call_ended: { label: 'Fin', color: 'bg-gray-400' },
}

const INTENT_RT_LABELS = {
  agendar_cita: 'Agendar',
  consulta_precio: 'Precio',
  consulta_horario: 'Horario',
  consulta_servicio: 'Servicio',
  queja: 'Queja',
  cancelar: 'Cancelar',
  seguimiento: 'Seguimiento',
  cotizacion: 'Cotización',
  soporte_tecnico: 'Soporte',
  otro: 'Otro',
}

export function CallDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, impersonatingClientId } = useAuth()
  const isAdmin = user?.role === 'admin' && !impersonatingClientId
  const [call, setCall] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/calls/${id}`)
      .then(setCall)
      .catch(() => navigate('/calls'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <PageLoader />
  if (!call) return null

  const duration = `${Math.floor(call.duration_seconds / 60)}:${String(call.duration_seconds % 60).padStart(2, '0')}`

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate('/calls')}>
          <ArrowLeft size={16} />
        </Button>
        <h1 className="text-2xl font-bold">Detalle de llamada</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1 space-y-3">
          <h2 className="text-sm font-semibold text-text-secondary">Info</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-muted">Dirección</span>
              <Badge variant={call.direction}>{call.direction}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Estado</span>
              <Badge variant={call.status}>{call.status}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Duración</span>
              <span className="font-mono">{duration}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Número</span>
              <span className="font-mono text-xs">{call.caller_number || '-'}</span>
            </div>
            {call.agent_name && (
              <div className="flex justify-between">
                <span className="text-text-muted">Agente</span>
                <span className="text-xs font-medium">{call.agent_name}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-text-muted">Fecha</span>
              <span className="text-xs">{new Date(call.started_at).toLocaleString('es-MX')}</span>
            </div>
          </div>

          <h2 className="text-sm font-semibold text-text-secondary pt-2">Consumo</h2>
          {isAdmin ? (
            /* Admin: desglose completo de costos internos */
            call.cost_breakdown?.lines?.length > 0 ? (
              <div className="space-y-1.5 text-sm font-mono">
                {call.cost_breakdown.lines.map((line, i) => (
                  <div key={i} className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-text-muted truncate">{line.label}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                        line.classification === 'platform'
                          ? 'bg-accent/15 text-accent'
                          : 'bg-bg-hover text-text-muted'
                      }`}>
                        {line.classification === 'platform' ? 'Plataforma' : 'Externo'}
                      </span>
                      {line.detail && (
                        <span className="text-[10px] text-text-muted/60 font-sans">{line.detail}</span>
                      )}
                    </div>
                    <span className={line.is_estimate ? 'text-text-muted' : ''}>
                      {line.is_estimate ? '~' : ''}${line.amount.toFixed(4)}
                    </span>
                  </div>
                ))}
                <div className="border-t border-border pt-1.5 space-y-1">
                  <div className="flex justify-between font-bold">
                    <span className="text-accent">Costo total</span>
                    <span className="text-accent">${call.cost_breakdown.platform_cost.toFixed(4)}</span>
                  </div>
                  {call.cost_breakdown.external_cost_estimate > 0 && (
                    <div className="flex justify-between text-text-muted text-xs">
                      <span>APIs externas (est.)</span>
                      <span>~${call.cost_breakdown.external_cost_estimate.toFixed(4)}</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-1 text-sm font-mono">
                <div className="flex justify-between"><span className="text-text-muted">LiveKit</span><span>${Number(call.cost_livekit).toFixed(4)}</span></div>
                <div className="flex justify-between"><span className="text-text-muted">STT</span><span>${Number(call.cost_stt).toFixed(4)}</span></div>
                <div className="flex justify-between"><span className="text-text-muted">LLM</span><span>${Number(call.cost_llm).toFixed(4)}</span></div>
                <div className="flex justify-between"><span className="text-text-muted">TTS</span><span>${Number(call.cost_tts).toFixed(4)}</span></div>
                <div className="flex justify-between"><span className="text-text-muted">Telefonía</span><span>${Number(call.cost_telephony).toFixed(4)}</span></div>
                <div className="flex justify-between border-t border-border pt-1 font-bold">
                  <span>Costo total</span><span className="text-accent">${Number(call.cost_total).toFixed(4)}</span>
                </div>
              </div>
            )
          ) : (
            /* Cliente: solo duración y créditos consumidos */
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-text-muted">Duracion</span>
                <span className="font-mono">{Math.floor(call.duration_seconds / 60)}:{String(call.duration_seconds % 60).padStart(2, '0')} min</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Creditos consumidos</span>
                <span className="font-mono font-bold text-accent">{(call.duration_seconds / 60).toFixed(2)}</span>
              </div>
            </div>
          )}

          {call.summary && (
            <>
              <h2 className="text-sm font-semibold text-text-secondary pt-2">Resumen</h2>
              <p className="text-sm text-text-secondary">{call.summary}</p>
            </>
          )}

          {/* Badge de grabación */}
          {call.recording_url && (
            <div className="pt-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium bg-accent/15 text-accent">
                <Mic size={12} />
                Grabacion disponible
              </span>
            </div>
          )}
        </Card>

        {/* Lifecycle — Ciclo de vida de la llamada */}
        {(call.disposition || call.disconnect_reason || call.call_events?.length > 0) && (
          <Card className="lg:col-span-2 space-y-4">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Clock size={16} className="text-accent" /> Ciclo de vida
            </h2>

            {/* Badges de disposition + disconnect */}
            <div className="flex flex-wrap gap-2">
              {call.disposition && DISPOSITION_CONFIG[call.disposition] && (() => {
                const cfg = DISPOSITION_CONFIG[call.disposition]
                const Icon = cfg.icon
                return (
                  <span className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1.5 ${cfg.color}`}>
                    <Icon size={12} />{cfg.label}
                  </span>
                )
              })()}
              {call.disconnect_reason && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-bg-hover text-text-secondary flex items-center gap-1.5">
                  {(() => {
                    const Icon = DISCONNECT_BY_ICONS[call.disconnect_by] || PhoneOff
                    return <Icon size={12} />
                  })()}
                  {DISCONNECT_LABELS[call.disconnect_reason] || call.disconnect_reason}
                </span>
              )}
            </div>

            {/* Tiempos */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {call.ring_duration_seconds != null && (
                <div className="bg-bg-secondary rounded-lg p-3 text-center">
                  <div className="text-lg font-mono font-bold text-text-primary">{call.ring_duration_seconds}s</div>
                  <div className="text-[10px] text-text-muted mt-0.5">Tiempo de ring</div>
                </div>
              )}
              {call.talk_duration_seconds != null && (
                <div className="bg-bg-secondary rounded-lg p-3 text-center">
                  <div className="text-lg font-mono font-bold text-accent">{call.talk_duration_seconds}s</div>
                  <div className="text-[10px] text-text-muted mt-0.5">Tiempo de habla</div>
                </div>
              )}
              <div className="bg-bg-secondary rounded-lg p-3 text-center">
                <div className="text-lg font-mono font-bold text-text-primary">{call.duration_seconds}s</div>
                <div className="text-[10px] text-text-muted mt-0.5">Duracion total</div>
              </div>
              {call.first_speech_at && call.answered_at && (
                <div className="bg-bg-secondary rounded-lg p-3 text-center">
                  <div className="text-lg font-mono font-bold text-purple-400">
                    {Math.max(0, Math.round((new Date(call.first_speech_at) - new Date(call.answered_at)) / 1000))}s
                  </div>
                  <div className="text-[10px] text-text-muted mt-0.5">Hasta 1er palabra</div>
                </div>
              )}
            </div>

            {/* Timeline de eventos */}
            {call.call_events?.length > 0 && (
              <div>
                <h3 className="text-xs text-text-muted mb-2">Timeline</h3>
                <div className="relative pl-4 space-y-2">
                  {/* Línea vertical */}
                  <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border" />
                  {call.call_events.map((ev, i) => {
                    const cfg = EVENT_CONFIG[ev.event] || { label: ev.event, color: 'bg-gray-500' }
                    const time = new Date(ev.timestamp)
                    const baseTime = call.call_events[0] ? new Date(call.call_events[0].timestamp) : time
                    const elapsed = Math.round((time - baseTime) / 1000)
                    return (
                      <div key={i} className="flex items-center gap-3 relative">
                        <div className={`w-2.5 h-2.5 rounded-full ${cfg.color} shrink-0 -ml-[5px] z-10 ring-2 ring-bg-primary`} />
                        <span className="text-xs font-medium text-text-primary w-28 truncate">{cfg.label}</span>
                        <span className="text-[10px] font-mono text-text-muted">+{elapsed}s</span>
                        {ev.details && Object.keys(ev.details).length > 0 && (
                          <span className="text-[10px] text-text-muted truncate max-w-[200px]">
                            {Object.entries(ev.details).filter(([,v]) => v).map(([k,v]) => `${k}: ${v}`).join(', ')}
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Sección Análisis IA */}
        {call.sentimiento && (
          <Card className="lg:col-span-2 space-y-4">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Brain size={16} className="text-accent" /> Análisis IA
            </h2>

            {/* Badges */}
            <div className="flex flex-wrap gap-2">
              <span className={`px-2 py-1 rounded text-xs font-medium ${SENTIMIENTO_COLORS[call.sentimiento] || 'bg-bg-hover text-text-secondary'}`}>
                {call.sentimiento}
              </span>
              {call.intencion && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-accent/15 text-accent">
                  <Target size={12} className="inline mr-1" />
                  {INTENCION_LABELS[call.intencion] || call.intencion}
                </span>
              )}
              {call.lead_score != null && (
                <span className="px-2 py-1 rounded text-xs font-medium bg-purple-500/15 text-purple-400">
                  <TrendingUp size={12} className="inline mr-1" />
                  Lead: {call.lead_score}/100
                </span>
              )}
              {call.quality_score != null && (
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  call.quality_score >= 80 ? 'bg-green-500/15 text-green-400' :
                  call.quality_score >= 50 ? 'bg-yellow-500/15 text-yellow-400' :
                  'bg-red-500/15 text-red-400'
                }`}>
                  <Star size={12} className="inline mr-1" />
                  Calidad: {call.quality_score}/100
                </span>
              )}
            </div>

            {/* Resumen IA */}
            {call.resumen_ia && (
              <div>
                <h3 className="text-xs text-text-muted mb-1">Resumen</h3>
                <p className="text-sm text-text-secondary">{call.resumen_ia}</p>
              </div>
            )}

            {/* Siguiente acción */}
            {call.siguiente_accion && call.siguiente_accion !== 'ninguna' && (
              <div>
                <h3 className="text-xs text-text-muted mb-1">Siguiente acción</h3>
                <p className="text-sm text-accent">{ACCION_LABELS[call.siguiente_accion] || call.siguiente_accion}</p>
              </div>
            )}

            {/* Preguntas sin respuesta */}
            {call.preguntas_sin_respuesta?.length > 0 && (
              <div>
                <h3 className="text-xs text-text-muted mb-1 flex items-center gap-1">
                  <AlertCircle size={12} className="text-yellow-400" /> Preguntas sin respuesta
                </h3>
                <ul className="space-y-1">
                  {call.preguntas_sin_respuesta.map((q, i) => (
                    <li key={i} className="text-sm text-yellow-400/80 flex items-start gap-2">
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-yellow-400 shrink-0" />
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        )}

        {/* Sentimiento en Tiempo Real */}
        {call.sentiment_realtime?.timeline?.length > 0 && (
          <Card className="lg:col-span-2 space-y-3">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Activity size={16} className="text-accent" /> Sentimiento en Tiempo Real
            </h2>

            {/* Stats chips */}
            <div className="flex flex-wrap gap-2">
              {call.sentiment_realtime.average_score != null && (
                <span className="px-2 py-1 rounded text-[11px] font-medium bg-bg-hover text-text-secondary">
                  Promedio: {call.sentiment_realtime.average_score.toFixed(1)}
                </span>
              )}
              {call.sentiment_realtime.dominant_sentiment && (
                <span className={`px-2 py-1 rounded text-[11px] font-medium bg-bg-hover ${
                  SENTIMENT_RT_TEXT[call.sentiment_realtime.dominant_sentiment] || 'text-text-secondary'
                }`}>
                  Dominante: {call.sentiment_realtime.dominant_sentiment}
                </span>
              )}
              {call.sentiment_realtime.max_consecutive_negative > 0 && (
                <span className="px-2 py-1 rounded text-[11px] font-medium bg-red-500/10 text-red-400">
                  {call.sentiment_realtime.max_consecutive_negative} negativo(s) consecutivos
                </span>
              )}
              {call.sentiment_realtime.switched_empathy && (
                <span className="px-2 py-1 rounded text-[11px] font-medium bg-accent/10 text-accent">
                  Empatia activada
                </span>
              )}
            </div>

            {/* Timeline bar */}
            <div>
              <div className="flex gap-px rounded overflow-hidden">
                {call.sentiment_realtime.timeline.map((t, i) => (
                  <div
                    key={i}
                    className={`group relative h-6 flex-1 min-w-[6px] ${SENTIMENT_RT_COLORS[t.sentiment] || 'bg-gray-500'} opacity-80 hover:opacity-100 transition-opacity cursor-default`}
                  >
                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10 w-48 pointer-events-none">
                      <div className="bg-bg-primary border border-border rounded px-2 py-1.5 text-[11px] shadow-lg">
                        <div className="font-medium text-text-primary mb-0.5">Turno {t.turn} — {t.sentiment}</div>
                        <div className="text-text-muted line-clamp-2">{t.text}</div>
                        {t.score != null && <div className="text-text-muted mt-0.5">Score: {t.score.toFixed(2)}</div>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {/* Turn labels */}
              <div className="flex gap-px mt-1">
                {call.sentiment_realtime.timeline.map((t, i) => (
                  <div key={i} className="flex-1 min-w-[6px] text-center">
                    <span className="text-[9px] text-text-muted">{t.turn}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 text-[10px] text-text-muted">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-green-400" />Positivo</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-gray-400" />Neutral</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-orange-400" />Negativo</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-red-400" />Frustrado</span>
            </div>
          </Card>
        )}

        {/* Intent Distribution */}
        {call.intent_realtime?.intent_counts && Object.keys(call.intent_realtime.intent_counts).length > 0 && (
          <Card className="lg:col-span-1 space-y-3">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Target size={16} className="text-accent" /> Intents Detectados
            </h2>

            {/* Primary intent badge */}
            {call.intent_realtime.primary_intent && (
              <div>
                <span className="px-2 py-1 rounded text-xs font-medium bg-accent/15 text-accent">
                  Principal: {INTENT_RT_LABELS[call.intent_realtime.primary_intent] || call.intent_realtime.primary_intent}
                </span>
              </div>
            )}

            {/* Horizontal bars */}
            <div className="space-y-2">
              {Object.entries(call.intent_realtime.intent_counts)
                .sort(([, a], [, b]) => b - a)
                .map(([intent, count]) => {
                  const maxCount = Math.max(...Object.values(call.intent_realtime.intent_counts))
                  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0
                  return (
                    <div key={intent} className="space-y-0.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-text-secondary">{INTENT_RT_LABELS[intent] || intent}</span>
                        <span className="text-text-muted font-mono">{count}</span>
                      </div>
                      <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
            </div>
          </Card>
        )}

        {/* Agent Turns Timeline (Modo Inteligente) */}
        {call.agent_turns?.length > 0 && (
          <Card className="lg:col-span-3 space-y-3">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Zap size={16} className="text-purple-400" /> Ruteo de Agentes (Modo Inteligente)
            </h2>
            <div className="flex flex-wrap gap-2">
              {call.agent_turns.map((turn, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border ${
                    turn.switched
                      ? 'border-purple-500/30 bg-purple-500/10'
                      : 'border-border bg-bg-secondary'
                  }`}
                >
                  <span className="text-text-muted font-mono">T{turn.turn}</span>
                  {turn.switched && <ArrowRightLeft size={10} className="text-purple-400" />}
                  <span className="font-medium">{turn.selected_agent_name}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-text-muted">
              {call.agent_turns.filter(t => t.switched).length} cambio(s) de agente en {call.agent_turns.length} turno(s)
            </p>
          </Card>
        )}

        {/* Grabación */}
        {call.recording_url && (
          <Card className="lg:col-span-3 space-y-3">
            <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Headphones size={16} className="text-accent" /> Grabacion
            </h2>
            <AudioPlayer
              url={call.recording_url}
              onDelete={() => {
                if (!call.id) return
                api.delete(`/calls/${call.id}/recording`)
                  .then(() => setCall(prev => ({ ...prev, recording_url: null })))
                  .catch(() => {})
              }}
            />
          </Card>
        )}

        <Card className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Transcripcion</h2>
          <TranscriptViewer transcript={call.transcript} />
        </Card>
      </div>
    </div>
  )
}
