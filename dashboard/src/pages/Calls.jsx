import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CallsTable } from '../components/CallsTable'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'

export function Calls() {
  const [calls, setCalls] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [clientId, setClientId] = useState(null)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (statusFilter) params.set('status', statusFilter)
    if (clientId) params.set('client_id', clientId)
    api.get(`/calls?${params}`)
      .then(setCalls)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page, statusFilter, clientId])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Llamadas</h1>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={v => { setClientId(v); setPage(1) }} />
          <div className="flex gap-2">
            {['', 'completed', 'failed', 'transferred'].map(s => (
              <Button
                key={s}
                variant={statusFilter === s ? 'primary' : 'secondary'}
                onClick={() => { setStatusFilter(s); setPage(1) }}
                className="text-xs"
              >
                {s || 'Todas'}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <Card>
        {loading ? <PageLoader /> : <CallsTable calls={calls} />}
      </Card>

      <div className="flex justify-center gap-2">
        <Button variant="secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
          Anterior
        </Button>
        <span className="px-4 py-2 text-sm text-text-muted">Página {page}</span>
        <Button variant="secondary" onClick={() => setPage(p => p + 1)} disabled={calls.length < 20}>
          Siguiente
        </Button>
      </div>
    </div>
  )
}
