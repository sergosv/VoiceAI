import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Shield, AlertTriangle, CheckCircle, XCircle, Activity, TrendingUp,
  Eye, Bell, Play, ChevronLeft, ChevronRight, Clock, Search,
  ShieldAlert, ShieldCheck, ShieldX, Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { ClientSelector } from '../components/ClientSelector'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Modal } from '../components/ui/Modal'
import { Table, Th, Td } from '../components/ui/Table'
import { PageLoader } from '../components/ui/Spinner'
import { EmptyState } from '../components/EmptyState'

const PERIOD_OPTIONS = [
  { value: 7, label: '7 dias' },
  { value: 30, label: '30 dias' },
  { value: 90, label: '90 dias' },
]

const FAILURE_TYPE_LABELS = {
  unauthorized_commitment: 'Compromisos no autorizados',
  hallucination: 'Alucinaciones',
  rag_miss: 'Info no encontrada',
  tool_error: 'Error en herramientas',
  prompt_leak: 'Filtracion de prompt',
  context_drift: 'Perdida de contexto',
  guardrail_bypass: 'Bypass de guardrails',
  wrong_escalation: 'Escalacion incorrecta',
}

const FAILURE_TYPE_COLORS = {
  unauthorized_commitment: 'bg-red-500',
  hallucination: 'bg-orange-500',
  rag_miss: 'bg-yellow-500',
  tool_error: 'bg-purple-500',
  prompt_leak: 'bg-pink-500',
  context_drift: 'bg-blue-500',
  guardrail_bypass: 'bg-rose-500',
  wrong_escalation: 'bg-amber-500',
}

const SEVERITY_COLORS = {
  critical: 'bg-red-500/20 text-red-400',
  high: 'bg-orange-500/20 text-orange-400',
  medium: 'bg-yellow-500/20 text-yellow-400',
  low: 'bg-blue-500/20 text-blue-400',
}

const SEVERITY_LABELS = {
  critical: 'Critico',
  high: 'Alto',
  medium: 'Medio',
  low: 'Bajo',
}

const SEVERITY_BORDER = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-500',
  medium: 'border-l-yellow-500',
  low: 'border-l-blue-500',
}

function scoreColor(score) {
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  return 'text-red-400'
}

function scoreBg(score) {
  if (score >= 80) return 'bg-green-500/20 text-green-400 border-green-500/30'
  if (score >= 60) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
  return 'bg-red-500/20 text-red-400 border-red-500/30'
}

function StatCard({ icon: Icon, label, value, sub, color = 'text-accent' }) {
  return (
    <Card className="flex items-center gap-3">
      <div className="p-2.5 rounded-lg bg-bg-hover">
        <Icon size={20} className={color} />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-text-muted">{label}</div>
        <div className={`text-xl font-bold ${color}`}>{value}</div>
        {sub && <div className="text-xs text-text-muted">{sub}</div>}
      </div>
    </Card>
  )
}

function FailureDistribution({ data }) {
  if (!data || Object.keys(data).length === 0) {
    return <p className="text-sm text-text-muted">Sin datos de distribucion</p>
  }

  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(...entries.map(([, v]) => v), 1)

  return (
    <div className="space-y-3">
      {entries.map(([type, count]) => (
        <div key={type} className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-text-secondary">
              {FAILURE_TYPE_LABELS[type] || type.replace(/_/g, ' ')}
            </span>
            <span className="font-mono text-text-muted">{count}</span>
          </div>
          <div className="w-full bg-bg-hover rounded-full h-4 overflow-hidden">
            <div
              className={`${FAILURE_TYPE_COLORS[type] || 'bg-accent'} h-full rounded-full transition-all`}
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function AlertCard({ alert, onAcknowledge, onViewCall }) {
  const severity = alert.severity || 'medium'
  return (
    <div
      className={`bg-bg-card/80 border border-border border-l-4 ${SEVERITY_BORDER[severity] || 'border-l-gray-500'} rounded-lg p-4 space-y-2`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <AlertTriangle
            size={16}
            className={severity === 'critical' ? 'text-red-400 shrink-0' : 'text-orange-400 shrink-0'}
          />
          <span className="font-semibold text-sm truncate">{alert.title}</span>
        </div>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono shrink-0 ${SEVERITY_COLORS[severity]}`}>
          {SEVERITY_LABELS[severity] || severity}
        </span>
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">{alert.description}</p>
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-3 text-xs text-text-muted">
          {alert.agent_name && <span>{alert.agent_name}</span>}
          <span className="flex items-center gap-1">
            <Clock size={11} />
            {new Date(alert.created_at).toLocaleString('es-MX', {
              dateStyle: 'short',
              timeStyle: 'short',
            })}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {alert.call_id && (
            <button
              type="button"
              onClick={() => onViewCall(alert.call_id)}
              className="text-xs text-accent hover:text-accent/80 cursor-pointer flex items-center gap-1"
            >
              <Eye size={12} /> Ver llamada
            </button>
          )}
          <button
            type="button"
            onClick={() => onAcknowledge(alert.id)}
            className="text-xs text-text-muted hover:text-green-400 cursor-pointer flex items-center gap-1"
          >
            <CheckCircle size={12} /> Marcar revisada
          </button>
        </div>
      </div>
    </div>
  )
}

function FailureDetailModal({ open, onClose, evaluation, failures, loadingFailures }) {
  if (!open) return null

  return (
    <Modal open={open} onClose={onClose} title="Detalle de fallos" maxWidth="max-w-2xl">
      {loadingFailures ? (
        <div className="flex justify-center py-8">
          <Loader2 size={24} className="animate-spin text-text-muted" />
        </div>
      ) : failures.length === 0 ? (
        <p className="text-sm text-text-muted text-center py-8">
          Sin fallos registrados para esta evaluacion.
        </p>
      ) : (
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {failures.map((f, idx) => (
            <div
              key={f.id || idx}
              className={`border border-border border-l-4 ${SEVERITY_BORDER[f.severity] || 'border-l-gray-500'} rounded-lg p-4 space-y-2`}
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${FAILURE_TYPE_COLORS[f.failure_type] ? `${FAILURE_TYPE_COLORS[f.failure_type]}/20 text-white` : 'bg-bg-hover text-text-secondary'}`}>
                  {FAILURE_TYPE_LABELS[f.failure_type] || f.failure_type}
                </span>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${SEVERITY_COLORS[f.severity]}`}>
                  {SEVERITY_LABELS[f.severity] || f.severity}
                </span>
                {f.turn_index != null && (
                  <span className="text-xs text-text-muted">Turno #{f.turn_index}</span>
                )}
              </div>
              <p className="text-sm text-text-primary">{f.description}</p>
              {f.evidence && (
                <div className="bg-bg-hover rounded-lg p-3 text-xs text-text-secondary italic border-l-2 border-text-muted">
                  &ldquo;{f.evidence}&rdquo;
                </div>
              )}
              {f.recommendation && (
                <div className="flex items-start gap-2 text-xs text-accent/80">
                  <TrendingUp size={12} className="mt-0.5 shrink-0" />
                  <span>{f.recommendation}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

export function QualityMonitor() {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [clientId, setClientId] = useState(null)

  // Data
  const [stats, setStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [evaluations, setEvaluations] = useState([])
  const [failures, setFailures] = useState([])

  // Pagination
  const [evalOffset, setEvalOffset] = useState(0)
  const [evalHasMore, setEvalHasMore] = useState(false)
  const EVAL_LIMIT = 20

  // Sweep state
  const [sweeping, setSweeping] = useState(false)

  // Failure detail modal
  const [selectedEval, setSelectedEval] = useState(null)
  const [modalFailures, setModalFailures] = useState([])
  const [loadingFailures, setLoadingFailures] = useState(false)

  const effectiveClientId = clientId || user?.client_id

  const loadData = useCallback(async () => {
    setLoading(true)
    const cq = effectiveClientId ? `&client_id=${effectiveClientId}` : ''
    try {
      const [statsRes, alertsRes, evalsRes] = await Promise.all([
        api.get(`/evaluations/stats?days=${days}${cq}`).catch(() => null),
        api.get(`/evaluations/alerts?${cq.replace('&', '')}${cq ? '&' : ''}acknowledged=false&limit=20`).catch(() => []),
        api.get(`/evaluations?${cq.replace('&', '')}${cq ? '&' : ''}limit=${EVAL_LIMIT}&offset=${evalOffset}`).catch(() => []),
      ])
      setStats(statsRes)
      setAlerts(Array.isArray(alertsRes) ? alertsRes : [])
      const evalList = Array.isArray(evalsRes) ? evalsRes : []
      setEvaluations(evalList)
      setEvalHasMore(evalList.length >= EVAL_LIMIT)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [days, effectiveClientId, evalOffset]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadData()
  }, [loadData])

  async function handleSweep() {
    setSweeping(true)
    try {
      await api.post('/evaluations/sweep?sample_size=10')
      toast.success('Evaluacion iniciada. Los resultados apareceran en unos momentos.')
      // Reload after short delay
      setTimeout(() => loadData(), 3000)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSweeping(false)
    }
  }

  async function handleAcknowledge(alertId) {
    try {
      await api.patch(`/evaluations/alerts/${alertId}/acknowledge`)
      setAlerts(prev => prev.filter(a => a.id !== alertId))
      toast.success('Alerta marcada como revisada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleViewFailures(evaluation) {
    setSelectedEval(evaluation)
    setLoadingFailures(true)
    setModalFailures([])
    try {
      const cq = effectiveClientId ? `&client_id=${effectiveClientId}` : ''
      const res = await api.get(
        `/evaluations/failures?evaluation_id=${evaluation.id}${cq}&limit=50`
      ).catch(() => [])
      setModalFailures(Array.isArray(res) ? res : [])
    } catch {
      setModalFailures([])
    } finally {
      setLoadingFailures(false)
    }
  }

  // Derived stats
  const totalEvaluated = stats?.total_evaluated ?? 0
  const avgScore = stats?.avg_score != null ? Math.round(stats.avg_score) : null
  const criticalCount = stats?.severity_distribution?.critical ?? 0
  const highCount = stats?.severity_distribution?.high ?? 0
  const zeroFailureRate = totalEvaluated > 0
    ? Math.round(((stats?.zero_failure_count ?? 0) / totalEvaluated) * 100)
    : 0
  const todayCount = stats?.today_count ?? 0

  if (loading && !stats) return <PageLoader />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield size={24} className="text-accent" /> Monitor de Calidad
        </h1>
        <div className="flex items-center gap-3 flex-wrap">
          <Button onClick={handleSweep} disabled={sweeping}>
            {sweeping ? (
              <Loader2 size={16} className="mr-1.5 animate-spin" />
            ) : (
              <Play size={16} className="mr-1.5" />
            )}
            {sweeping ? 'Evaluando...' : 'Evaluar ahora'}
          </Button>
          <div className="flex rounded-lg border border-border overflow-hidden">
            {PERIOD_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => { setDays(opt.value); setEvalOffset(0) }}
                className={`px-3 py-1.5 text-xs font-medium cursor-pointer transition-colors ${
                  days === opt.value
                    ? 'bg-accent text-bg-primary'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {user?.role === 'admin' && (
            <ClientSelector value={clientId} onChange={(v) => { setClientId(v); setEvalOffset(0) }} />
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard
          icon={Activity}
          label="Llamadas evaluadas"
          value={totalEvaluated}
        />
        <StatCard
          icon={TrendingUp}
          label="Score promedio"
          value={avgScore != null ? avgScore : '--'}
          color={avgScore != null ? scoreColor(avgScore) : 'text-text-muted'}
        />
        <StatCard
          icon={ShieldX}
          label="Fallos criticos"
          value={criticalCount}
          color="text-red-400"
        />
        <StatCard
          icon={ShieldAlert}
          label="Fallos altos"
          value={highCount}
          color="text-orange-400"
        />
        <StatCard
          icon={ShieldCheck}
          label="Tasa sin fallos"
          value={`${zeroFailureRate}%`}
          color="text-green-400"
        />
        <StatCard
          icon={Clock}
          label="Evaluaciones hoy"
          value={todayCount}
          color="text-accent"
        />
      </div>

      {/* Alerts section */}
      <div>
        <h2 className="text-lg font-semibold flex items-center gap-2 mb-3">
          <Bell size={18} className="text-accent" /> Alertas de Calidad
          {alerts.length > 0 && (
            <span className="ml-2 px-2 py-0.5 rounded-full text-xs font-mono bg-red-500/20 text-red-400">
              {alerts.length}
            </span>
          )}
        </h2>
        {alerts.length === 0 ? (
          <Card>
            <EmptyState
              icon={CheckCircle}
              title="Sin alertas pendientes"
              description="No hay alertas de calidad sin revisar. El sistema esta funcionando correctamente."
              className="!py-10"
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {alerts.map(alert => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={handleAcknowledge}
                onViewCall={(callId) => navigate(`/calls/${callId}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Failure Distribution + Recent Evaluations row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Failure Distribution */}
        <Card>
          <h3 className="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
            <XCircle size={16} /> Distribucion de Fallos
          </h3>
          <FailureDistribution data={stats?.failure_distribution} />
        </Card>

        {/* Recent Evaluations table */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
              <Search size={16} /> Evaluaciones Recientes
            </h3>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setEvalOffset(Math.max(0, evalOffset - EVAL_LIMIT))}
                disabled={evalOffset === 0}
                className="p-1 rounded hover:bg-bg-hover text-text-muted disabled:opacity-30 cursor-pointer disabled:cursor-default transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-xs text-text-muted font-mono">
                {evaluations.length > 0 ? `${evalOffset + 1}-${evalOffset + evaluations.length}` : '0'}
              </span>
              <button
                type="button"
                onClick={() => setEvalOffset(evalOffset + EVAL_LIMIT)}
                disabled={!evalHasMore}
                className="p-1 rounded hover:bg-bg-hover text-text-muted disabled:opacity-30 cursor-pointer disabled:cursor-default transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {evaluations.length === 0 ? (
            <EmptyState
              icon={Shield}
              title="Sin evaluaciones"
              description="Ejecuta una evaluacion para detectar fallos silenciosos en tus agentes."
              action={handleSweep}
              actionLabel="Evaluar ahora"
              actionIcon={Play}
              className="!py-10"
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <thead>
                  <tr>
                    <Th>Score</Th>
                    <Th>Agente</Th>
                    <Th>Fallos</Th>
                    <Th>Criticos</Th>
                    <Th>Resumen</Th>
                    <Th>Fecha</Th>
                    <Th className="w-20">Acciones</Th>
                  </tr>
                </thead>
                <tbody>
                  {evaluations.map(ev => {
                    const score = ev.overall_score != null ? Math.round(ev.overall_score) : null
                    return (
                      <tr
                        key={ev.id}
                        className="hover:bg-bg-hover transition-colors cursor-pointer"
                        onClick={() => navigate(`/calls/${ev.call_id}`)}
                      >
                        <Td>
                          {score != null ? (
                            <span className={`inline-flex items-center justify-center w-10 h-10 rounded-full border text-sm font-bold ${scoreBg(score)}`}>
                              {score}
                            </span>
                          ) : (
                            <span className="text-text-muted">--</span>
                          )}
                        </Td>
                        <Td>
                          <span className="text-sm">{ev.agent_name || ev.agent_id?.slice(0, 8) || '--'}</span>
                        </Td>
                        <Td>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              if (ev.failures_found > 0) handleViewFailures(ev)
                            }}
                            className={`font-mono text-sm ${
                              ev.failures_found > 0
                                ? 'text-orange-400 hover:text-orange-300 underline decoration-dotted cursor-pointer'
                                : 'text-green-400 cursor-default'
                            }`}
                          >
                            {ev.failures_found ?? 0}
                          </button>
                        </Td>
                        <Td>
                          <span className={`font-mono text-sm ${ev.critical_failures > 0 ? 'text-red-400 font-bold' : 'text-text-muted'}`}>
                            {ev.critical_failures ?? 0}
                          </span>
                        </Td>
                        <Td>
                          <span className="text-xs text-text-secondary max-w-[220px] truncate block" title={ev.evaluation_data?.summary}>
                            {ev.evaluation_data?.summary || ev.status || '--'}
                          </span>
                        </Td>
                        <Td>
                          <span className="text-xs text-text-muted flex items-center gap-1">
                            <Clock size={11} />
                            {ev.created_at
                              ? new Date(ev.created_at).toLocaleString('es-MX', {
                                  dateStyle: 'short',
                                  timeStyle: 'short',
                                })
                              : '--'}
                          </span>
                        </Td>
                        <Td>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/calls/${ev.call_id}`)
                            }}
                            className="p-1.5 rounded hover:bg-accent/10 text-text-muted hover:text-accent transition-colors cursor-pointer"
                            title="Ver llamada"
                          >
                            <Eye size={14} />
                          </button>
                        </Td>
                      </tr>
                    )
                  })}
                </tbody>
              </Table>
            </div>
          )}
        </Card>
      </div>

      {/* Failure Detail Modal */}
      <FailureDetailModal
        open={!!selectedEval}
        onClose={() => setSelectedEval(null)}
        evaluation={selectedEval}
        failures={modalFailures}
        loadingFailures={loadingFailures}
      />
    </div>
  )
}
