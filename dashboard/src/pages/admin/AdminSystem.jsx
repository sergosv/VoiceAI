import { useEffect, useState, useRef } from 'react'
import {
  Activity, Users, Building2, Phone, DollarSign, RefreshCw, Loader2,
  AlertTriangle, Megaphone, Clock, CreditCard, CheckCircle, XCircle,
} from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

function StatCard({ icon: Icon, label, value, color = 'text-accent', subtext }) {
  return (
    <Card className="text-center">
      <Icon size={22} className={`${color} mx-auto mb-2`} />
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-text-muted uppercase tracking-wider mt-1">{label}</p>
      {subtext && <p className="text-[10px] text-text-muted mt-0.5">{subtext}</p>}
    </Card>
  )
}

export function AdminSystem() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const toast = useToast()
  const intervalRef = useRef(null)

  async function fetchData(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    try {
      const result = await api.get('/admin/system/overview')
      setData(result)
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
  }, [])

  if (loading) return <PageLoader />

  if (!data) {
    return (
      <EmptyState
        icon={Activity}
        title="Error cargando datos"
        description="No se pudo obtener la informacion del sistema."
      />
    )
  }

  const {
    total_clients = 0,
    total_users = 0,
    calls_24h = 0,
    revenue_30d = 0,
    recent_payments = [],
    failed_webhooks = 0,
    active_campaigns = 0,
  } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Activity size={22} className="text-accent" />
            Sistema
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Vista general de la plataforma — se actualiza cada 60s
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

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={Building2}
          label="Total Clientes"
          value={total_clients}
          color="text-accent"
        />
        <StatCard
          icon={Users}
          label="Total Usuarios"
          value={total_users}
          color="text-purple-400"
        />
        <StatCard
          icon={Phone}
          label="Llamadas (24h)"
          value={calls_24h}
          color="text-green-400"
        />
        <StatCard
          icon={DollarSign}
          label="Revenue (30d)"
          value={`$${typeof revenue_30d === 'number' ? revenue_30d.toLocaleString('es-MX', { minimumFractionDigits: 2 }) : revenue_30d}`}
          color="text-yellow-400"
        />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card className={`flex items-center gap-4 ${failed_webhooks > 0 ? 'border-red-500/30' : ''}`}>
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            failed_webhooks > 0 ? 'bg-red-500/10' : 'bg-bg-secondary'
          }`}>
            <AlertTriangle size={20} className={failed_webhooks > 0 ? 'text-red-400' : 'text-text-muted'} />
          </div>
          <div>
            <p className={`text-xl font-bold ${failed_webhooks > 0 ? 'text-red-400' : 'text-text-primary'}`}>
              {failed_webhooks}
            </p>
            <p className="text-[10px] text-text-muted uppercase tracking-wider">Webhooks Fallidos</p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
            <Megaphone size={20} className="text-accent" />
          </div>
          <div>
            <p className="text-xl font-bold text-text-primary">{active_campaigns}</p>
            <p className="text-[10px] text-text-muted uppercase tracking-wider">Campanas Activas</p>
          </div>
        </Card>

        <Card className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
            <Clock size={20} className="text-green-400" />
          </div>
          <div>
            <p className="text-xs font-medium text-text-primary">
              {new Date().toLocaleString('es-MX', {
                timeZone: 'America/Mexico_City',
                hour: '2-digit', minute: '2-digit', second: '2-digit',
                day: '2-digit', month: 'short',
              })}
            </p>
            <p className="text-[10px] text-text-muted uppercase tracking-wider">Hora CDMX</p>
          </div>
        </Card>
      </div>

      {/* Recent payments */}
      <Card>
        <h2 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
          <CreditCard size={16} className="text-accent" />
          Pagos Recientes
        </h2>
        {(!recent_payments || recent_payments.length === 0) ? (
          <div className="text-center py-8">
            <CreditCard size={32} className="mx-auto text-text-muted mb-2" />
            <p className="text-sm text-text-muted">Sin pagos recientes</p>
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Fecha</Th>
                <Th>Cliente</Th>
                <Th>Monto</Th>
                <Th>Creditos</Th>
                <Th>Estado</Th>
              </tr>
            </thead>
            <tbody>
              {recent_payments.map((p, i) => (
                <tr key={p.id || i} className="hover:bg-bg-hover/50 transition-colors">
                  <Td>
                    <span className="text-text-muted text-xs">
                      {p.created_at
                        ? new Date(p.created_at).toLocaleDateString('es-MX', {
                            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                          })
                        : '--'}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-text-primary text-sm">{p.client_name || p.client_id || '--'}</span>
                  </Td>
                  <Td>
                    <span className="text-text-primary font-mono text-sm">
                      ${typeof p.amount === 'number' ? p.amount.toFixed(2) : p.amount || '0.00'}
                    </span>
                  </Td>
                  <Td>
                    <span className="text-accent font-mono text-sm">
                      {p.credits || p.credits_added || '--'}
                    </span>
                  </Td>
                  <Td>
                    <Badge variant={
                      p.status === 'completed' || p.status === 'succeeded' ? 'completed'
                        : p.status === 'failed' ? 'failed'
                        : 'pending'
                    }>
                      <span className="inline-flex items-center gap-1">
                        {p.status === 'completed' || p.status === 'succeeded'
                          ? <CheckCircle size={10} />
                          : p.status === 'failed'
                            ? <XCircle size={10} />
                            : <Clock size={10} />}
                        {p.status || 'pendiente'}
                      </span>
                    </Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
