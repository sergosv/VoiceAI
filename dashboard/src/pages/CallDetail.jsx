import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone } from 'lucide-react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { TranscriptViewer } from '../components/TranscriptViewer'
import { PageLoader } from '../components/ui/Spinner'

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

        <Card className="lg:col-span-2">
          <h2 className="text-sm font-semibold text-text-secondary mb-4">Transcripción</h2>
          <TranscriptViewer transcript={call.transcript} />
        </Card>
      </div>
    </div>
  )
}
