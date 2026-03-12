import { useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, RotateCcw, Loader2 } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

export function AdminWebhookDLQ() {
  const [deliveries, setDeliveries] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [retryingId, setRetryingId] = useState(null)
  const perPage = 50
  const toast = useToast()

  async function fetchDLQ(p = page) {
    try {
      const data = await api.get(`/admin/webhook-dlq?page=${p}&per_page=${perPage}`)
      setDeliveries(data.data || [])
      setTotal(data.total || 0)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.get(`/admin/webhook-dlq?page=${page}&per_page=${perPage}`)
      .then(data => {
        if (!cancelled) {
          setDeliveries(data.data || [])
          setTotal(data.total || 0)
        }
      })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page])

  async function handleRetry(delivery) {
    setRetryingId(delivery.id)
    try {
      await api.post(`/admin/webhook-dlq/${delivery.id}/retry`)
      setDeliveries(prev => prev.filter(d => d.id !== delivery.id))
      setTotal(prev => prev - 1)
      toast.success('Webhook reenviado')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setRetryingId(null)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  function fmtDate(d) {
    if (!d) return '--'
    return new Date(d).toLocaleString('es-MX', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  function truncate(str, len = 40) {
    if (!str) return '--'
    return str.length > len ? str.slice(0, len) + '...' : str
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <AlertCircle size={22} className="text-accent" />
            Webhook DLQ
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {total} entrega{total !== 1 ? 's' : ''} fallida{total !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => { setLoading(true); fetchDLQ() }}
        >
          <RefreshCw size={14} className="mr-2 inline" />
          Actualizar
        </Button>
      </div>

      <Card>
        {loading ? <PageLoader /> : deliveries.length === 0 ? (
          <EmptyState
            icon={AlertCircle}
            title="Sin entregas fallidas"
            description="No hay webhooks en la dead letter queue."
          />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Fecha</Th>
                  <Th>Evento</Th>
                  <Th>Cliente</Th>
                  <Th>URL</Th>
                  <Th>Status</Th>
                  <Th>Error</Th>
                  <Th>Intentos</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map(d => (
                  <tr key={d.id} className="hover:bg-bg-hover/50 transition-colors">
                    <Td>
                      <span className="text-text-muted text-xs whitespace-nowrap">{fmtDate(d.delivered_at)}</span>
                    </Td>
                    <Td>
                      <Badge variant="info">{d.event || '--'}</Badge>
                    </Td>
                    <Td>
                      <span className="text-text-primary text-sm">{d.client_name}</span>
                    </Td>
                    <Td>
                      <span className="font-mono text-xs text-text-muted" title={d.endpoint_url || ''}>
                        {truncate(d.endpoint_url)}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-xs text-text-muted">
                        {d.status_code || '--'}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-xs text-danger" title={d.error || ''}>
                        {truncate(d.error, 30)}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-text-secondary text-sm">{d.attempt ?? '--'}</span>
                    </Td>
                    <Td>
                      <div className="flex items-center justify-end">
                        <button
                          onClick={() => handleRetry(d)}
                          disabled={retryingId === d.id}
                          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors cursor-pointer disabled:opacity-50"
                          title="Reintentar"
                        >
                          {retryingId === d.id
                            ? <Loader2 size={15} className="animate-spin" />
                            : <RotateCcw size={15} />}
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                <span className="text-xs text-text-muted">
                  Pagina {page} de {totalPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
