import { useEffect, useState } from 'react'
import {
  Activity, CheckCircle, AlertTriangle, XCircle, RefreshCw,
  ArrowRight, Loader2, Server, Zap, Mic, MessageSquare, Volume2,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { PageLoader } from '../components/ui/Spinner'
import { EmptyState } from '../components/EmptyState'

const COMPONENT_ICONS = {
  STT: Mic,
  LLM: MessageSquare,
  TTS: Volume2,
}

const HEALTH_CONFIG = {
  healthy: { color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/20', icon: CheckCircle, label: 'Operativo' },
  degraded: { color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20', icon: AlertTriangle, label: 'Degradado' },
  critical: { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', icon: XCircle, label: 'Critico' },
  unknown: { color: 'text-text-muted', bg: 'bg-bg-secondary border-border', icon: Activity, label: 'Sin datos' },
}

const CIRCUIT_CONFIG = {
  closed: { color: 'text-green-400', label: 'Cerrado (OK)' },
  open: { color: 'text-red-400', label: 'Abierto (Caido)' },
  half_open: { color: 'text-yellow-400', label: 'Semi-abierto (Probando)' },
}

function HealthBadge({ health }) {
  const cfg = HEALTH_CONFIG[health] || HEALTH_CONFIG.unknown
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${cfg.bg} ${cfg.color}`}>
      <Icon size={12} />
      {cfg.label}
    </span>
  )
}

function ProviderCard({ provider }) {
  const CompIcon = COMPONENT_ICONS[provider.component] || Server
  const cfg = HEALTH_CONFIG[provider.health] || HEALTH_CONFIG.unknown

  return (
    <Card className={`border ${provider.health === 'healthy' ? 'border-border' : cfg.bg}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${cfg.bg}`}>
            <CompIcon size={20} className={cfg.color} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{provider.provider}</h3>
            <p className="text-xs text-text-muted">{provider.component}</p>
          </div>
        </div>
        <HealthBadge health={provider.health} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="text-center">
          <p className="text-lg font-bold text-text-primary">{provider.total_calls}</p>
          <p className="text-[10px] text-text-muted">Llamadas</p>
        </div>
        <div className="text-center">
          <p className={`text-lg font-bold ${provider.success_rate >= 95 ? 'text-green-400' : provider.success_rate >= 80 ? 'text-yellow-400' : 'text-red-400'}`}>
            {provider.success_rate}%
          </p>
          <p className="text-[10px] text-text-muted">Exito</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold text-red-400">{provider.failed}</p>
          <p className="text-[10px] text-text-muted">Fallos</p>
        </div>
      </div>

      {provider.last_seen && (
        <p className="mt-3 text-[10px] text-text-muted">
          Ultima actividad: {new Date(provider.last_seen).toLocaleString('es-MX')}
        </p>
      )}
    </Card>
  )
}

function FallbackChains({ chains }) {
  if (!chains || Object.keys(chains).length === 0) return null

  const LABELS = { stt: 'STT', tts: 'TTS', llm: 'LLM' }

  return (
    <Card>
      <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
        <Zap size={16} className="text-accent" />
        Cadenas de Fallback
      </h3>
      <div className="space-y-3">
        {Object.entries(chains).map(([component, chain]) => (
          <div key={component}>
            <p className="text-xs font-medium text-text-secondary mb-1.5">{LABELS[component] || component}</p>
            <div className="space-y-1">
              {Object.entries(chain).map(([primary, fallback]) => (
                <div key={primary} className="flex items-center gap-2 text-xs text-text-muted">
                  <span className="text-text-primary font-mono">{primary}</span>
                  <ArrowRight size={12} />
                  <span className="text-accent font-mono">{fallback}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function CircuitBreakers({ circuits }) {
  if (!circuits || Object.keys(circuits).length === 0) {
    return (
      <Card>
        <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <Activity size={16} className="text-accent" />
          Circuit Breakers
        </h3>
        <p className="text-xs text-text-muted">
          Los circuit breakers se activan en el runtime del agente. Los datos aparecen cuando hay llamadas activas.
        </p>
      </Card>
    )
  }

  return (
    <Card>
      <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
        <Activity size={16} className="text-accent" />
        Circuit Breakers
      </h3>
      <div className="space-y-2">
        {Object.entries(circuits).map(([name, info]) => {
          const cfg = CIRCUIT_CONFIG[info.state] || CIRCUIT_CONFIG.closed
          return (
            <div key={name} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <span className="text-sm text-text-primary font-mono">{name}</span>
              <div className="flex items-center gap-3">
                {info.failure_count > 0 && (
                  <span className="text-xs text-red-400">{info.failure_count} fallos</span>
                )}
                <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

export function ProviderHealth() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  async function fetchData(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)

    try {
      const res = await fetch('/api/admin/provider-health')
      if (!res.ok) throw new Error('Error fetching health')
      const json = await res.json()
      setData(json)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => fetchData(true), 30000) // Auto-refresh cada 30s
    return () => clearInterval(interval)
  }, [])

  if (loading) return <PageLoader />

  if (!data) {
    return <EmptyState icon={Server} title="Error cargando datos" description="No se pudo obtener el estado de providers" />
  }

  const providers = data.providers || []
  const healthyCt = providers.filter(p => p.health === 'healthy').length
  const degradedCt = providers.filter(p => p.health === 'degraded').length
  const criticalCt = providers.filter(p => p.health === 'critical').length

  // Agrupar por componente
  const grouped = {}
  providers.forEach(p => {
    if (!grouped[p.component]) grouped[p.component] = []
    grouped[p.component].push(p)
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Server size={22} className="text-accent" />
            Estado de Providers
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Basado en las ultimas {data.total_calls_analyzed} llamadas
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchData(true)}
          disabled={refreshing}
        >
          {refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Actualizar
        </Button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="text-center border-green-500/20">
          <CheckCircle size={24} className="text-green-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-green-400">{healthyCt}</p>
          <p className="text-xs text-text-muted">Operativos</p>
        </Card>
        <Card className="text-center border-yellow-500/20">
          <AlertTriangle size={24} className="text-yellow-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-yellow-400">{degradedCt}</p>
          <p className="text-xs text-text-muted">Degradados</p>
        </Card>
        <Card className="text-center border-red-500/20">
          <XCircle size={24} className="text-red-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-red-400">{criticalCt}</p>
          <p className="text-xs text-text-muted">Criticos</p>
        </Card>
      </div>

      {/* Provider cards por componente */}
      {Object.entries(grouped).map(([component, provs]) => (
        <div key={component}>
          <h2 className="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
            {(() => { const I = COMPONENT_ICONS[component] || Server; return <I size={16} /> })()}
            {component === 'STT' ? 'Speech-to-Text' : component === 'LLM' ? 'Language Model' : component === 'TTS' ? 'Text-to-Speech' : component}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {provs.map(p => (
              <ProviderCard key={`${p.component}/${p.provider}`} provider={p} />
            ))}
          </div>
        </div>
      ))}

      {providers.length === 0 && (
        <EmptyState
          icon={Activity}
          title="Sin datos de providers"
          description="Aun no hay llamadas registradas para analizar la salud de los providers."
        />
      )}

      {/* Circuit Breakers + Fallback Chains */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CircuitBreakers circuits={data.circuits} />
        <FallbackChains chains={data.fallback_chains} />
      </div>
    </div>
  )
}
