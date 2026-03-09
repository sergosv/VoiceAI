import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { EmptyState } from '../components/EmptyState'
import {
  ClipboardList, BarChart3, CheckCircle, XCircle, Hash,
  Percent, Trophy, Calendar, Bot, Minus, ChevronLeft, ChevronRight,
} from 'lucide-react'

const MODE_OPTIONS = [
  { value: '', label: 'Todos los modos' },
  { value: 'survey', label: 'Encuesta' },
  { value: 'quiz', label: 'Cuestionario' },
  { value: 'negotiation', label: 'Negociaci\u00f3n' },
  { value: 'interview', label: 'Entrevista' },
]

const MODE_LABELS = {
  survey: 'Encuesta',
  quiz: 'Cuestionario',
  negotiation: 'Negociaci\u00f3n',
  interview: 'Entrevista',
}

const MODE_BADGE_COLORS = {
  survey: 'bg-blue-500/20 text-blue-400',
  quiz: 'bg-warning/20 text-warning',
  negotiation: 'bg-accent/20 text-accent',
  interview: 'bg-bg-hover text-text-secondary',
}

const COMPLETED_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'true', label: 'Completadas' },
  { value: 'false', label: 'Incompletas' },
]

const PER_PAGE = 50

function StatCard({ icon: Icon, label, value, color = 'text-accent' }) {
  return (
    <Card className="flex items-center gap-3">
      <div className="p-2.5 rounded-lg bg-bg-hover">
        <Icon size={20} className={color} />
      </div>
      <div>
        <div className="text-xs text-text-muted">{label}</div>
        <div className={`text-xl font-bold ${color}`}>{value}</div>
      </div>
    </Card>
  )
}

function ModeBadge({ mode }) {
  const color = MODE_BADGE_COLORS[mode] || 'bg-bg-hover text-text-secondary'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${color}`}>
      {MODE_LABELS[mode] || mode}
    </span>
  )
}

function ScoreDisplay({ score, maxScore }) {
  if (score == null) return <span className="text-text-muted">--</span>
  if (maxScore) {
    const pct = Math.round((score / maxScore) * 100)
    return (
      <span className="font-mono">
        {score}/{maxScore}{' '}
        <span className="text-text-muted text-xs">({pct}%)</span>
      </span>
    )
  }
  return <span className="font-mono">{score}</span>
}

function PassedIcon({ passed }) {
  if (passed === true) return <CheckCircle size={16} className="text-green-400" />
  if (passed === false) return <XCircle size={16} className="text-red-400" />
  return <Minus size={14} className="text-text-muted" />
}

export function ConversationResults() {
  const { user } = useAuth()
  const toast = useToast()

  const [clientId, setClientId] = useState(null)
  const [results, setResults] = useState([])
  const [stats, setStats] = useState(null)
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedResult, setSelectedResult] = useState(null)

  // Filtros
  const [modeFilter, setModeFilter] = useState('')
  const [completedFilter, setCompletedFilter] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [page, setPage] = useState(0) // offset-based: page * PER_PAGE

  const effectiveClientId = user?.role === 'client' ? user.client_id : clientId

  // Cargar agentes cuando cambia el client
  useEffect(() => {
    if (!effectiveClientId) {
      setAgents([])
      return
    }
    api.get(`/clients/${effectiveClientId}/agents`)
      .then(setAgents)
      .catch(() => setAgents([]))
  }, [effectiveClientId])

  // Cargar resultados
  useEffect(() => {
    if (!effectiveClientId) {
      setResults([])
      setStats(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)

    const params = new URLSearchParams({ limit: PER_PAGE, offset: page * PER_PAGE })
    if (modeFilter) params.set('mode', modeFilter)
    if (agentFilter) params.set('agent_id', agentFilter)
    if (completedFilter) params.set('completed', completedFilter)

    const statsAgentId = agentFilter || (agents.length > 0 ? '' : '')
    const statsParams = new URLSearchParams()
    if (modeFilter) statsParams.set('mode', modeFilter)
    const statsUrl = agentFilter
      ? `/conversation-results/${effectiveClientId}/stats/${agentFilter}?${statsParams}`
      : `/conversation-results/${effectiveClientId}/stats/?${statsParams}`

    Promise.all([
      api.get(`/conversation-results/${effectiveClientId}?${params}`),
      api.get(statsUrl).catch(() => null),
    ]).then(([data, st]) => {
      if (cancelled) return
      setResults(data || [])
      setStats(st)
    }).catch(err => {
      if (!cancelled) toast.error(err.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => { cancelled = true }
  }, [effectiveClientId, modeFilter, completedFilter, agentFilter, page]) // eslint-disable-line react-hooks/exhaustive-deps

  function getAgentName(agentId) {
    const agent = agents.find(a => a.id === agentId)
    return agent?.name || agentId?.slice(0, 8) || '--'
  }

  async function openDetail(result) {
    try {
      const detail = await api.get(`/conversation-results/${effectiveClientId}/${result.id}`)
      setSelectedResult(detail)
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ClipboardList size={24} /> Resultados de Conversaci&oacute;n
        </h1>
        <ClientSelector value={clientId} onChange={v => { setClientId(v); setPage(0); setAgentFilter('') }} />
      </div>

      {!effectiveClientId ? (
        <Card>
          <EmptyState
            icon={ClipboardList}
            title="Selecciona un cliente"
            description="Elige un cliente para ver los resultados de sus conversaciones."
          />
        </Card>
      ) : loading ? (
        <PageLoader />
      ) : (
        <>
          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <StatCard icon={Hash} label="Total" value={stats.total ?? 0} />
              <StatCard icon={CheckCircle} label="Completadas" value={stats.completed ?? 0} color="text-green-400" />
              <StatCard
                icon={Percent}
                label="Tasa completaci&oacute;n"
                value={`${stats.completion_rate ?? 0}%`}
                color="text-blue-400"
              />
              <StatCard icon={Trophy} label="Aprobadas" value={stats.passed ?? 0} color="text-emerald-400" />
              <StatCard
                icon={BarChart3}
                label="Tasa aprobaci&oacute;n"
                value={`${stats.pass_rate ?? 0}%`}
                color="text-purple-400"
              />
              <StatCard
                icon={BarChart3}
                label="Promedio score"
                value={`${stats.avg_score_pct ?? 0}%`}
                color="text-yellow-400"
              />
            </div>
          )}

          {/* Filtros */}
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={modeFilter}
              onChange={e => { setModeFilter(e.target.value); setPage(0) }}
              className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {MODE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <select
              value={completedFilter}
              onChange={e => { setCompletedFilter(e.target.value); setPage(0) }}
              className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {COMPLETED_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            <select
              value={agentFilter}
              onChange={e => { setAgentFilter(e.target.value); setPage(0) }}
              className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              <option value="">Todos los agentes</option>
              {agents.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>

            {(modeFilter || completedFilter || agentFilter) && (
              <button
                onClick={() => { setModeFilter(''); setCompletedFilter(''); setAgentFilter(''); setPage(0) }}
                className="text-xs text-text-muted hover:text-accent transition-colors cursor-pointer"
              >
                Limpiar filtros
              </button>
            )}
          </div>

          {/* Tabla */}
          <Card>
            {results.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="Sin resultados"
                description="No se encontraron resultados de conversaci&oacute;n con los filtros seleccionados."
              />
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Modo</Th>
                    <Th>Agente</Th>
                    <Th>Completada</Th>
                    <Th>Score</Th>
                    <Th>Aprobado</Th>
                    <Th>Fecha</Th>
                  </tr>
                </thead>
                <tbody>
                  {results.map(r => (
                    <tr
                      key={r.id}
                      className="hover:bg-bg-hover cursor-pointer transition-colors"
                      onClick={() => openDetail(r)}
                    >
                      <Td><ModeBadge mode={r.mode} /></Td>
                      <Td>
                        <span className="flex items-center gap-1 text-sm">
                          <Bot size={14} className="text-text-muted" />
                          {getAgentName(r.agent_id)}
                        </span>
                      </Td>
                      <Td>
                        {r.completed ? (
                          <CheckCircle size={16} className="text-green-400" />
                        ) : (
                          <XCircle size={16} className="text-text-muted" />
                        )}
                      </Td>
                      <Td><ScoreDisplay score={r.score} maxScore={r.max_score} /></Td>
                      <Td><PassedIcon passed={r.passed} /></Td>
                      <Td>
                        <span className="flex items-center gap-1 text-xs text-text-muted">
                          <Calendar size={12} />
                          {r.created_at ? new Date(r.created_at).toLocaleDateString('es-MX', {
                            day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
                          }) : '--'}
                        </span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>

          {/* Paginaci&oacute;n */}
          <div className="flex justify-center gap-2">
            <Button
              variant="secondary"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft size={14} className="mr-1" /> Anterior
            </Button>
            <span className="px-4 py-2 text-sm text-text-muted">
              P&aacute;gina {page + 1}
            </span>
            <Button
              variant="secondary"
              onClick={() => setPage(p => p + 1)}
              disabled={results.length < PER_PAGE}
            >
              Siguiente <ChevronRight size={14} className="ml-1" />
            </Button>
          </div>
        </>
      )}

      {/* Modal detalle */}
      {selectedResult && (
        <Modal
          open={true}
          title="Detalle de Resultado"
          onClose={() => setSelectedResult(null)}
          maxWidth="max-w-xl"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-text-muted mb-1">Modo</div>
                <ModeBadge mode={selectedResult.mode} />
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">Agente</div>
                <span className="text-sm font-medium">{getAgentName(selectedResult.agent_id)}</span>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">Completada</div>
                <span className="flex items-center gap-1 text-sm">
                  {selectedResult.completed ? (
                    <><CheckCircle size={14} className="text-green-400" /> S&iacute;</>
                  ) : (
                    <><XCircle size={14} className="text-red-400" /> No</>
                  )}
                </span>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">Score</div>
                <ScoreDisplay score={selectedResult.score} maxScore={selectedResult.max_score} />
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">Aprobado</div>
                <span className="flex items-center gap-1 text-sm">
                  <PassedIcon passed={selectedResult.passed} />
                  {selectedResult.passed === true ? ' S\u00ed' : selectedResult.passed === false ? ' No' : ' N/A'}
                </span>
              </div>
              <div>
                <div className="text-xs text-text-muted mb-1">Fecha</div>
                <span className="text-sm">
                  {selectedResult.created_at
                    ? new Date(selectedResult.created_at).toLocaleString('es-MX', {
                        day: '2-digit', month: 'long', year: 'numeric',
                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                      })
                    : '--'}
                </span>
              </div>
            </div>

            {/* Datos extra del resultado si existen */}
            {selectedResult.data && Object.keys(selectedResult.data).length > 0 && (
              <div>
                <div className="text-xs text-text-muted mb-2">Datos del resultado</div>
                <pre className="bg-bg-primary border border-border rounded-lg p-3 text-xs overflow-x-auto max-h-60 whitespace-pre-wrap">
                  {JSON.stringify(selectedResult.data, null, 2)}
                </pre>
              </div>
            )}

            {selectedResult.id && (
              <div className="pt-2 border-t border-border">
                <span className="text-[10px] text-text-muted font-mono">ID: {selectedResult.id}</span>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
