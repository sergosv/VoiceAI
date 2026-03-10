import { useEffect, useState } from 'react'
import { ClipboardList, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { PageLoader } from '../components/ui/Spinner'

const ACTION_OPTIONS = [
  { value: '', label: 'Todas las acciones' },
  { value: 'agent.create', label: 'Agente creado' },
  { value: 'agent.update', label: 'Agente actualizado' },
  { value: 'agent.delete', label: 'Agente eliminado' },
  { value: 'apikey.create', label: 'API Key creada' },
  { value: 'apikey.revoke', label: 'API Key revocada' },
  { value: 'billing.purchase', label: 'Compra de creditos' },
  { value: 'client.gdpr_delete', label: 'Datos eliminados (GDPR)' },
]

const ACTION_LABELS = {
  'agent.create': { label: 'Agente creado', color: 'bg-green-500/20 text-green-400' },
  'agent.update': { label: 'Agente actualizado', color: 'bg-blue-500/20 text-blue-400' },
  'agent.delete': { label: 'Agente eliminado', color: 'bg-red-500/20 text-red-400' },
  'apikey.create': { label: 'API Key creada', color: 'bg-green-500/20 text-green-400' },
  'apikey.revoke': { label: 'API Key revocada', color: 'bg-orange-500/20 text-orange-400' },
  'billing.purchase': { label: 'Compra de creditos', color: 'bg-cyan-500/20 text-cyan-400' },
  'client.gdpr_delete': { label: 'Datos eliminados (GDPR)', color: 'bg-red-500/20 text-red-400' },
}

function relativeTime(dateStr) {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diff = Math.floor((now - then) / 1000)

  if (diff < 60) return 'hace unos segundos'
  if (diff < 3600) {
    const m = Math.floor(diff / 60)
    return `hace ${m} min`
  }
  if (diff < 86400) {
    const h = Math.floor(diff / 3600)
    return `hace ${h} hora${h > 1 ? 's' : ''}`
  }
  if (diff < 604800) {
    const d = Math.floor(diff / 86400)
    return `hace ${d} dia${d > 1 ? 's' : ''}`
  }
  return new Date(dateStr).toLocaleDateString('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function formatDetails(details, action) {
  if (!details || typeof details !== 'object') return '-'
  const parts = []
  if (details.agent_name) parts.push(details.agent_name)
  if (details.agent_id && !details.agent_name) parts.push(`ID: ${details.agent_id}`)
  if (details.credits) parts.push(`${details.credits} creditos`)
  if (details.amount) parts.push(`$${details.amount}`)
  if (details.key_name) parts.push(details.key_name)
  if (details.reason) parts.push(details.reason)
  return parts.length > 0 ? parts.join(' — ') : '-'
}

export function AuditLog() {
  const toast = useToast()
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')
  const perPage = 50

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: perPage })
    if (actionFilter) params.set('action', actionFilter)
    api.get(`/dashboard/audit-logs?${params}`)
      .then(data => {
        if (!cancelled) {
          setLogs(data.data || [])
          setTotal(data.total || 0)
        }
      })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page, actionFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  const totalPages = Math.max(1, Math.ceil(total / perPage))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ClipboardList size={24} /> Actividad
        </h1>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <select
          value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          className="bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {ACTION_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <span className="text-sm text-text-muted">
          {total} registro{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <PageLoader />
      ) : logs.length === 0 ? (
        <div className="bg-bg-secondary border border-border rounded-xl p-12 text-center">
          <ClipboardList size={48} className="mx-auto text-text-muted mb-4 opacity-40" />
          <p className="text-text-muted text-lg">No hay actividad registrada aun</p>
        </div>
      ) : (
        <div className="bg-bg-secondary border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text-muted">
                  <th className="px-4 py-3 font-medium">Fecha</th>
                  <th className="px-4 py-3 font-medium">Accion</th>
                  <th className="px-4 py-3 font-medium">Recurso</th>
                  <th className="px-4 py-3 font-medium">Detalles</th>
                  <th className="px-4 py-3 font-medium">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {logs.map(log => {
                  const actionInfo = ACTION_LABELS[log.action] || {
                    label: log.action,
                    color: 'bg-gray-500/20 text-gray-400',
                  }
                  return (
                    <tr key={log.id} className="hover:bg-bg-hover transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap text-text-muted" title={log.created_at}>
                        {relativeTime(log.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${actionInfo.color}`}>
                          {actionInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {log.resource_type || '-'}
                        {log.resource_id && (
                          <span className="text-text-muted text-xs ml-1">({log.resource_id.slice(0, 8)})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-text-secondary max-w-xs truncate">
                        {formatDetails(log.details, log.action)}
                      </td>
                      <td className="px-4 py-3 text-text-muted font-mono text-xs">
                        {log.ip_address || '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border">
              <span className="text-sm text-text-muted">
                Pagina {page} de {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1.5 rounded-lg border border-border text-text-secondary hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1.5 rounded-lg border border-border text-text-secondary hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
