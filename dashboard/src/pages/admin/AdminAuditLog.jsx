import { useEffect, useState, useRef } from 'react'
import {
  ScrollText, RefreshCw, Loader2, ChevronLeft, ChevronRight,
  Search, Filter, X, Eye,
} from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Input'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

const ACTION_OPTIONS = [
  { value: '', label: 'Todas las acciones' },
  { value: 'agent.create', label: 'Agente creado' },
  { value: 'agent.update', label: 'Agente actualizado' },
  { value: 'agent.delete', label: 'Agente eliminado' },
  { value: 'apikey.create', label: 'API Key creada' },
  { value: 'apikey.revoke', label: 'API Key revocada' },
  { value: 'billing.purchase', label: 'Compra de creditos' },
  { value: 'client.gdpr_delete', label: 'Datos eliminados (GDPR)' },
  { value: 'client.create', label: 'Cliente creado' },
  { value: 'client.update', label: 'Cliente actualizado' },
  { value: 'user.update', label: 'Usuario actualizado' },
  { value: 'webhook.create', label: 'Webhook creado' },
  { value: 'webhook.delete', label: 'Webhook eliminado' },
  { value: 'mcp.create', label: 'MCP Server creado' },
  { value: 'mcp.delete', label: 'MCP Server eliminado' },
]

const RESOURCE_OPTIONS = [
  { value: '', label: 'Todos los recursos' },
  { value: 'agent', label: 'Agente' },
  { value: 'client', label: 'Cliente' },
  { value: 'user', label: 'Usuario' },
  { value: 'apikey', label: 'API Key' },
  { value: 'billing', label: 'Billing' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'mcp_server', label: 'MCP Server' },
  { value: 'document', label: 'Documento' },
]

const ACTION_COLORS = {
  'agent.create': 'bg-green-500/20 text-green-400',
  'agent.update': 'bg-blue-500/20 text-blue-400',
  'agent.delete': 'bg-red-500/20 text-red-400',
  'apikey.create': 'bg-green-500/20 text-green-400',
  'apikey.revoke': 'bg-orange-500/20 text-orange-400',
  'billing.purchase': 'bg-cyan-500/20 text-cyan-400',
  'client.gdpr_delete': 'bg-red-500/20 text-red-400',
  'client.create': 'bg-green-500/20 text-green-400',
  'client.update': 'bg-blue-500/20 text-blue-400',
  'user.update': 'bg-purple-500/20 text-purple-400',
  'webhook.create': 'bg-green-500/20 text-green-400',
  'webhook.delete': 'bg-red-500/20 text-red-400',
  'mcp.create': 'bg-green-500/20 text-green-400',
  'mcp.delete': 'bg-red-500/20 text-red-400',
}

function formatDate(dateStr) {
  if (!dateStr) return '--'
  return new Date(dateStr).toLocaleDateString('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDetails(details) {
  if (!details || typeof details !== 'object') return null
  const entries = Object.entries(details)
  if (entries.length === 0) return null
  return entries
}

export function AdminAuditLog() {
  const toast = useToast()
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [expandedRow, setExpandedRow] = useState(null)
  const intervalRef = useRef(null)

  // Filters
  const [actionFilter, setActionFilter] = useState('')
  const [resourceFilter, setResourceFilter] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const perPage = 50

  async function fetchData(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)

    try {
      const params = new URLSearchParams({ page, per_page: perPage })
      if (actionFilter) params.set('action', actionFilter)
      if (resourceFilter) params.set('resource_type', resourceFilter)
      if (userSearch.trim()) params.set('user_id', userSearch.trim())
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)

      const result = await api.get(`/admin/audit-logs?${params}`)
      setLogs(result.data || [])
      setTotal(result.total || 0)
    } catch (err) {
      if (!isRefresh) toast.error(err.message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    intervalRef.current = setInterval(() => fetchData(true), 60000)
    return () => clearInterval(intervalRef.current)
  }, [page, actionFilter, resourceFilter, userSearch, dateFrom, dateTo]) // eslint-disable-line react-hooks/exhaustive-deps

  function clearFilters() {
    setActionFilter('')
    setResourceFilter('')
    setUserSearch('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  const hasFilters = actionFilter || resourceFilter || userSearch || dateFrom || dateTo
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  if (loading && !refreshing) return <PageLoader />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <ScrollText size={22} className="text-accent" />
            Audit Log Global
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Registro de todas las acciones en la plataforma — se actualiza cada 60s
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchData(true)}
          disabled={refreshing}
        >
          {refreshing
            ? <Loader2 size={14} className="animate-spin mr-2 inline" />
            : <RefreshCw size={14} className="mr-2 inline" />}
          Actualizar
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-accent" />
          <h2 className="text-sm font-semibold text-text-primary">Filtros</h2>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="ml-auto text-xs text-text-muted hover:text-accent flex items-center gap-1 cursor-pointer"
            >
              <X size={12} />
              Limpiar filtros
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <Select
            label="Accion"
            options={ACTION_OPTIONS}
            value={actionFilter}
            onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          />
          <Select
            label="Recurso"
            options={RESOURCE_OPTIONS}
            value={resourceFilter}
            onChange={e => { setResourceFilter(e.target.value); setPage(1) }}
          />
          <Input
            label="User ID"
            placeholder="UUID del usuario..."
            value={userSearch}
            onChange={e => { setUserSearch(e.target.value); setPage(1) }}
          />
          <Input
            label="Desde"
            type="date"
            value={dateFrom}
            onChange={e => { setDateFrom(e.target.value); setPage(1) }}
          />
          <Input
            label="Hasta"
            type="date"
            value={dateTo}
            onChange={e => { setDateTo(e.target.value); setPage(1) }}
          />
        </div>
      </Card>

      {/* Results count */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-text-muted">
          {total} registro{total !== 1 ? 's' : ''}
          {hasFilters ? ' (filtrado)' : ''}
        </span>
      </div>

      {/* Table */}
      {logs.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="Sin registros"
          description={hasFilters
            ? 'No se encontraron registros con los filtros aplicados.'
            : 'No hay actividad registrada aun.'}
        />
      ) : (
        <Card className="!p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <thead>
                <tr>
                  <Th>Fecha</Th>
                  <Th>Usuario</Th>
                  <Th>Accion</Th>
                  <Th>Recurso</Th>
                  <Th>Cliente</Th>
                  <Th>Detalles</Th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => {
                  const actionColor = ACTION_COLORS[log.action] || 'bg-gray-500/20 text-gray-400'
                  const details = formatDetails(log.details)
                  const isExpanded = expandedRow === log.id

                  return (
                    <tr
                      key={log.id}
                      className="hover:bg-bg-hover/50 transition-colors"
                    >
                      <Td>
                        <span className="text-text-muted text-xs whitespace-nowrap">
                          {formatDate(log.created_at)}
                        </span>
                      </Td>
                      <Td>
                        <div className="min-w-0">
                          {log.user_email ? (
                            <span className="text-text-primary text-sm truncate block max-w-[180px]" title={log.user_email}>
                              {log.user_email}
                            </span>
                          ) : log.user_id ? (
                            <span className="text-text-muted text-xs font-mono" title={log.user_id}>
                              {log.user_id.slice(0, 8)}...
                            </span>
                          ) : (
                            <span className="text-text-muted text-xs">Sistema</span>
                          )}
                        </div>
                      </Td>
                      <Td>
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${actionColor}`}>
                          {log.action}
                        </span>
                      </Td>
                      <Td>
                        <span className="text-text-secondary text-sm">
                          {log.entity_type || '-'}
                        </span>
                        {log.entity_id && (
                          <span className="text-text-muted text-xs ml-1 font-mono">
                            ({log.entity_id.slice(0, 8)})
                          </span>
                        )}
                      </Td>
                      <Td>
                        {log.client_name ? (
                          <span className="text-text-primary text-sm">{log.client_name}</span>
                        ) : log.client_id ? (
                          <span className="text-text-muted text-xs font-mono" title={log.client_id}>
                            {log.client_id.slice(0, 8)}...
                          </span>
                        ) : (
                          <span className="text-text-muted text-xs">--</span>
                        )}
                      </Td>
                      <Td>
                        {details ? (
                          <button
                            onClick={() => setExpandedRow(isExpanded ? null : log.id)}
                            className="flex items-center gap-1 text-accent hover:text-accent/80 text-xs cursor-pointer"
                            title="Ver detalles"
                          >
                            <Eye size={12} />
                            {isExpanded ? 'Ocultar' : `${details.length} campo${details.length > 1 ? 's' : ''}`}
                          </button>
                        ) : (
                          <span className="text-text-muted text-xs">--</span>
                        )}
                        {isExpanded && details && (
                          <div className="mt-2 p-2 bg-bg-primary rounded-lg text-xs space-y-1 max-w-xs">
                            {details.map(([k, v]) => (
                              <div key={k} className="flex gap-2">
                                <span className="text-text-muted font-mono shrink-0">{k}:</span>
                                <span className="text-text-secondary break-all">
                                  {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
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
        </Card>
      )}
    </div>
  )
}
