import { useEffect, useState } from 'react'
import { Phone, Clock, DollarSign, FileText } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { StatsCard } from '../components/StatsCard'
import { UsageChart } from '../components/UsageChart'
import { CallsTable } from '../components/CallsTable'
import { Card } from '../components/ui/Card'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { OnboardingChecklist } from '../components/OnboardingChecklist'

export function Dashboard() {
  const toast = useToast()
  const [overview, setOverview] = useState(null)
  const [usage, setUsage] = useState(null)
  const [recentCalls, setRecentCalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const cq = clientId ? `client_id=${clientId}&` : ''
    Promise.all([
      api.get(`/dashboard/overview?${cq}`),
      api.get(`/dashboard/usage?${cq}days=30`),
      api.get(`/calls?${cq}per_page=5`),
    ]).then(([ov, us, calls]) => {
      if (cancelled) return
      setOverview(ov)
      setUsage(us)
      setRecentCalls(calls)
    }).catch(err => {
      if (!cancelled) toast.error(err.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [clientId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <PageLoader />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Inicio</h1>
          {overview?.client_name && (
            <p className="text-text-secondary text-sm mt-1">{overview.client_name}</p>
          )}
        </div>
        <ClientSelector value={clientId} onChange={setClientId} />
      </div>

      {/* Onboarding */}
      <OnboardingChecklist />

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          icon={Phone}
          label="Llamadas hoy"
          value={overview?.calls_today ?? 0}
          sub={`${overview?.total_calls ?? 0} total`}
        />
        <StatsCard
          icon={Clock}
          label="Minutos hoy"
          value={`${overview?.minutes_today?.toFixed(1) ?? 0}`}
          sub={`${overview?.total_minutes?.toFixed(1) ?? 0} total`}
        />
        <StatsCard
          icon={DollarSign}
          label="Costo plataforma hoy"
          value={`$${overview?.platform_cost_today?.toFixed(2) ?? '0.00'}`}
          sub={
            overview?.external_cost_today > 0
              ? `+~$${overview.external_cost_today.toFixed(2)} APIs ext.`
              : `$${overview?.platform_cost_total?.toFixed(2) ?? '0.00'} total plataforma`
          }
        />
        <StatsCard
          icon={FileText}
          label="Documentos"
          value={overview?.active_documents ?? 0}
          sub="en knowledge base"
        />
      </div>

      {/* Chart */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Llamadas (últimos 30 días)</h2>
        <UsageChart data={usage?.data} dataKey="calls" label="Llamadas" />
      </Card>

      {/* Recent calls */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Llamadas recientes</h2>
        <CallsTable calls={recentCalls} />
      </Card>
    </div>
  )
}
