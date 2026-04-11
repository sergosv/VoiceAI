import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { useAuth } from '../context/AuthContext'
import { PhoneCall, Clock, Bot, XCircle, CheckCircle, AlertTriangle, RefreshCw, ChevronLeft, ChevronRight, Play, Trash2, Megaphone, PhoneIncoming } from 'lucide-react'

const STATUS_CONFIG = {
  pending: { label: 'Pendiente', color: 'bg-yellow-500/20 text-yellow-400', icon: Clock },
  in_progress: { label: 'En curso', color: 'bg-blue-500/20 text-blue-400', icon: RefreshCw },
  completed: { label: 'Completado', color: 'bg-green-500/20 text-green-400', icon: CheckCircle },
  failed: { label: 'Fallido', color: 'bg-red-500/20 text-red-400', icon: AlertTriangle },
  cancelled: { label: 'Cancelado', color: 'bg-gray-500/20 text-gray-400', icon: XCircle },
}

const ORIGIN_CONFIG = {
  campaign: { label: 'Campaña', color: 'bg-purple-500/15 text-purple-400', icon: Megaphone },
  inbound: { label: 'Recepción', color: 'bg-cyan-500/15 text-cyan-400', icon: PhoneIncoming },
  outbound: { label: 'Outbound', color: 'bg-orange-500/15 text-orange-400', icon: PhoneCall },
}

export function Callbacks() {
  const [callbacks, setCallbacks] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [processing, setProcessing] = useState(false)
  const toast = useToast()
  const confirmDialog = useConfirm()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const perPage = 15

  function load() {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: perPage })
    if (statusFilter) params.set('status', statusFilter)
    api.get(`/callbacks?${params}`)
      .then(res => {
        setCallbacks(res.data || [])
        setTotal(res.total || 0)
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, statusFilter])

  async function handleCancel(id) {
    const confirmed = await confirmDialog({
      title: 'Cancelar callback',
      message: 'El callback no se ejecutara. Continuar?',
      confirmText: 'Cancelar callback',
      variant: 'warning',
    })
    if (!confirmed) return
    try {
      await api.patch(`/callbacks/${id}/cancel`, { reason: 'Cancelado desde dashboard' })
      toast.success('Callback cancelado')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleDelete(id) {
    const confirmed = await confirmDialog({
      title: 'Eliminar callback',
      message: 'El callback se eliminara permanentemente. Continuar?',
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!confirmed) return
    try {
      await api.delete(`/callbacks/${id}`)
      toast.success('Callback eliminado')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleProcess() {
    setProcessing(true)
    try {
      const stats = await api.post('/callbacks/process')
      toast.success(`Procesados: ${stats.processed}, OK: ${stats.succeeded}, Fallidos: ${stats.failed}`)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setProcessing(false)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  if (loading && page === 1) return <PageLoader />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Callbacks programados</h1>
          <p className="text-sm text-text-muted mt-1">
            Devoluciones de llamada prometidas por tus agentes
          </p>
        </div>
        {isAdmin && (
          <Button onClick={handleProcess} disabled={processing} variant="secondary">
            <Play size={14} />
            {processing ? 'Procesando...' : 'Ejecutar pendientes'}
          </Button>
        )}
      </div>

      {/* Filtros */}
      <div className="flex gap-2 flex-wrap">
        {['', 'pending', 'completed', 'failed', 'cancelled'].map(s => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1) }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              statusFilter === s
                ? 'bg-accent text-bg-primary'
                : 'bg-bg-secondary text-text-secondary hover:bg-bg-hover'
            }`}
          >
            {s === '' ? 'Todos' : STATUS_CONFIG[s]?.label || s}
          </button>
        ))}
      </div>

      {/* Lista */}
      {callbacks.length === 0 ? (
        <Card className="text-center py-12 text-text-muted">
          <PhoneCall size={32} className="mx-auto mb-3 opacity-40" />
          <p>No hay callbacks {statusFilter ? `con estado "${STATUS_CONFIG[statusFilter]?.label}"` : ''}</p>
          <p className="text-xs mt-1">Los callbacks se crean cuando el agente promete devolver una llamada</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {callbacks.map(cb => {
            const cfg = STATUS_CONFIG[cb.status] || STATUS_CONFIG.pending
            const Icon = cfg.icon
            const originCfg = ORIGIN_CONFIG[cb.origin_type] || ORIGIN_CONFIG.inbound
            const OriginIcon = originCfg.icon
            const scheduledDate = new Date(cb.scheduled_at)
            const isPast = scheduledDate < new Date()

            return (
              <Card key={cb.id} className="flex items-center gap-4 p-4">
                {/* Status icon */}
                <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${cfg.color}`}>
                  <Icon size={18} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm font-medium">{cb.phone}</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${cfg.color}`}>
                      {cfg.label}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium flex items-center gap-1 ${originCfg.color}`}>
                      <OriginIcon size={11} /> {originCfg.label}
                    </span>
                    {cb.agent_name && (
                      <span className="flex items-center gap-1 text-[11px] text-text-muted">
                        <Bot size={12} /> {cb.agent_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {scheduledDate.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })}
                      {' '}
                      {scheduledDate.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                      {cb.status === 'pending' && isPast && (
                        <span className="text-yellow-400 ml-1">(vencido)</span>
                      )}
                    </span>
                    {cb.attempts > 0 && (
                      <span>Intentos: {cb.attempts}/{cb.max_attempts}</span>
                    )}
                  </div>
                  {cb.context && (
                    <p className="text-xs text-text-muted mt-1 line-clamp-2">{cb.context}</p>
                  )}
                  {cb.failure_reason && cb.status === 'failed' && (
                    <p className="text-xs text-red-400 mt-1">{cb.failure_reason}</p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {cb.origin_call_id && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => window.location.href = `/app/calls/${cb.origin_call_id}`}
                      title="Ver llamada original"
                    >
                      <PhoneCall size={14} />
                    </Button>
                  )}
                  {cb.status === 'pending' && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleCancel(cb.id)}
                      title="Cancelar (no ejecutar)"
                    >
                      <XCircle size={14} />
                    </Button>
                  )}
                  {cb.status !== 'in_progress' && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDelete(cb.id)}
                      title="Eliminar permanentemente"
                    >
                      <Trash2 size={14} />
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">{total} callbacks</span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft size={14} />
            </Button>
            <span className="text-xs text-text-muted">{page} / {totalPages}</span>
            <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
