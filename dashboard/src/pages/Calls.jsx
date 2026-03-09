import { useEffect, useState } from 'react'
import { Phone, Download } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { CallsTable } from '../components/CallsTable'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { FilterBar } from '../components/FilterBar'

const STATUS_OPTIONS = [
  { value: 'completed', label: 'Completada' },
  { value: 'failed', label: 'Fallida' },
  { value: 'transferred', label: 'Transferida' },
]

const DIRECTION_OPTIONS = [
  { value: 'inbound', label: 'Entrante' },
  { value: 'outbound', label: 'Saliente' },
]

export function Calls() {
  const { user } = useAuth()
  const toast = useToast()
  const [calls, setCalls] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [directionFilter, setDirectionFilter] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [agents, setAgents] = useState([])
  const [clientId, setClientId] = useState(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // Cargar lista de agentes
  useEffect(() => {
    const cid = user?.role === 'admin' ? clientId : user?.client_id
    if (!cid) { setAgents([]); setAgentFilter(''); return }
    api.get(`/clients/${cid}/agents`)
      .then(data => setAgents(data || []))
      .catch(() => setAgents([]))
  }, [clientId, user]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (statusFilter) params.set('status', statusFilter)
    if (directionFilter) params.set('direction', directionFilter)
    if (agentFilter) params.set('agent_id', agentFilter)
    if (clientId) params.set('client_id', clientId)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    api.get(`/calls?${params}`)
      .then(data => { if (!cancelled) setCalls(data) })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page, statusFilter, directionFilter, agentFilter, clientId, dateFrom, dateTo]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleClear() {
    setStatusFilter('')
    setDirectionFilter('')
    setAgentFilter('')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Phone size={24} /> Llamadas
        </h1>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              const params = new URLSearchParams()
              if (clientId) params.set('client_id', clientId)
              if (statusFilter) params.set('status', statusFilter)
              if (dateFrom) params.set('date_from', dateFrom)
              if (dateTo) params.set('date_to', dateTo)
              api.download(`/calls/export/csv?${params}`).catch(e => toast.error(e.message))
            }}
            className="text-xs"
            title="Exportar a CSV"
          >
            <Download size={14} className="mr-1" /> CSV
          </Button>
          <ClientSelector value={clientId} onChange={v => { setClientId(v); setPage(1) }} />
        </div>
      </div>

      <FilterBar
        filters={[
          { key: 'status', label: 'Estado', options: STATUS_OPTIONS },
          { key: 'direction', label: 'Dirección', options: DIRECTION_OPTIONS },
        ]}
        values={{ status: statusFilter, direction: directionFilter }}
        onChange={(key, value) => {
          if (key === 'status') { setStatusFilter(value); setPage(1) }
          if (key === 'direction') { setDirectionFilter(value); setPage(1) }
        }}
        dateRange
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateChange={(from, to) => { setDateFrom(from); setDateTo(to); setPage(1) }}
        onClear={handleClear}
      />

      {agents.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-text-muted uppercase tracking-wide">Agente:</span>
          <select
            value={agentFilter}
            onChange={e => { setAgentFilter(e.target.value); setPage(1) }}
            className="bg-bg-secondary border border-border rounded px-2 py-1 text-xs text-text-primary focus:border-accent outline-none"
          >
            <option value="">Todos los agentes</option>
            {agents.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      )}

      <Card>
        {loading ? <PageLoader /> : <CallsTable calls={calls} />}
      </Card>

      <div className="flex justify-center gap-2">
        <Button variant="secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
          Anterior
        </Button>
        <span className="px-4 py-2 text-sm text-text-muted">Pagina {page}</span>
        <Button variant="secondary" onClick={() => setPage(p => p + 1)} disabled={calls.length < 20}>
          Siguiente
        </Button>
      </div>
    </div>
  )
}
