import { useEffect, useState } from 'react'
import { Phone } from 'lucide-react'
import { api } from '../lib/api'
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

export function Calls() {
  const toast = useToast()
  const [calls, setCalls] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [clientId, setClientId] = useState(null)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (statusFilter) params.set('status', statusFilter)
    if (clientId) params.set('client_id', clientId)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    api.get(`/calls?${params}`)
      .then(data => { if (!cancelled) setCalls(data) })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page, statusFilter, clientId, dateFrom, dateTo]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleClear() {
    setStatusFilter('')
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
        <ClientSelector value={clientId} onChange={v => { setClientId(v); setPage(1) }} />
      </div>

      <FilterBar
        filters={[
          { key: 'status', label: 'Estado', options: STATUS_OPTIONS },
        ]}
        values={{ status: statusFilter }}
        onChange={(key, value) => { setStatusFilter(value); setPage(1) }}
        dateRange
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateChange={(from, to) => { setDateFrom(from); setDateTo(to); setPage(1) }}
        onClear={handleClear}
      />

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
