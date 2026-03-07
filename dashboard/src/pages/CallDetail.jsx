import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, Brain, AlertCircle, Target, TrendingUp, Zap, ArrowRightLeft, Star, Activity } from 'lucide-react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { TranscriptViewer } from '../components/TranscriptViewer'
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

          <h2 className="text-sm font-semibold text-text-secondary pt-2">Costos</h2>
          {call.cost_breakdown?.lines?.length > 0 ? (
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
                  </div>
                  <span className={line.is_estimate ? 'text-text-muted' : ''}>
                    {line.is_estimate ? '~' : ''}${line.amount.toFixed(4)}
                  </span>
                </div>
              ))}
              <div className="border-t border-border pt-1.5 space-y-1">
                <div className="flex justify-between font-bold">
                  <span className="text-accent">Plataforma</span>
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
                <span>Total</span><span className="text-accent">${Number(call.cost_total).toFixed(4)}</span>
              </div>
            </div>
          )}

          {call.summary && (
            <>
              <h2 className="text-sm font-semibold text-text-secondary pt-2">Resumen</h2>
              <p className="text-sm text-text-secondary">{call.summary}</p>
            </>
          )}
        </Card>

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

        <Card className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Transcripción</h2>
          <TranscriptViewer transcript={call.transcript} />
        </Card>
      </div>
    </div>
  )
}
