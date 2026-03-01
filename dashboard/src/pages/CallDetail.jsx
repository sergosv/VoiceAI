import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, Brain, AlertCircle, Target, TrendingUp, Zap, ArrowRightLeft } from 'lucide-react'
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
