import { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader, Spinner } from '../components/ui/Spinner'
import { EmptyState } from '../components/EmptyState'
import {
  FlaskConical,
  Plus,
  Sparkles,
  Play,
  Pencil,
  Trash2,
  Star,
  Clock,
  MessageSquare,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Target,
  Lightbulb,
  Users,
  ListChecks,
  ChevronRight,
  X,
  Bot,
  User,
  Minus,
  BarChart3,
  FolderOpen,
} from 'lucide-react'

const DIFFICULTY_CONFIG = {
  easy: { label: 'Facil', color: 'text-emerald-400', bg: 'bg-emerald-400/15 border-emerald-400/30' },
  medium: { label: 'Media', color: 'text-amber-400', bg: 'bg-amber-400/15 border-amber-400/30' },
  hard: { label: 'Dificil', color: 'text-red-400', bg: 'bg-red-400/15 border-red-400/30' },
}

const STATUS_CONFIG = {
  pending: { label: 'Pendiente', color: 'bg-gray-400', pulse: false },
  running: { label: 'En curso', color: 'bg-blue-400', pulse: true },
  completed: { label: 'Completada', color: 'bg-emerald-400', pulse: false },
  failed: { label: 'Fallida', color: 'bg-red-400', pulse: false },
}

const DIFFICULTY_OPTIONS = [
  { value: 'easy', label: 'Facil' },
  { value: 'medium', label: 'Media' },
  { value: 'hard', label: 'Dificil' },
]

function scoreColor(score) {
  if (score == null) return 'text-text-muted'
  if (score >= 71) return 'text-emerald-400'
  if (score >= 41) return 'text-amber-400'
  return 'text-red-400'
}

function scoreBgRing(score) {
  if (score == null) return 'border-border'
  if (score >= 71) return 'border-emerald-400/50'
  if (score >= 41) return 'border-amber-400/50'
  return 'border-red-400/50'
}

function formatDuration(seconds) {
  if (!seconds) return '--'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ---------- Subcomponents ----------

function DifficultyBadge({ difficulty }) {
  const cfg = DIFFICULTY_CONFIG[difficulty] || DIFFICULTY_CONFIG.medium
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}

function StatusDot({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending
  return (
    <span className="relative flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${cfg.color} ${cfg.pulse ? 'animate-pulse' : ''}`} />
      <span className="text-xs text-text-secondary">{cfg.label}</span>
    </span>
  )
}

function TagPill({ tag }) {
  return (
    <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent/10 text-accent/80 border border-accent/20">
      {tag}
    </span>
  )
}

function TabNav({ activeTab, setActiveTab }) {
  const tabs = [
    { key: 'personas', label: 'Personas', icon: Users },
    { key: 'resultados', label: 'Resultados', icon: BarChart3 },
    { key: 'suites', label: 'Suites', icon: FolderOpen },
  ]
  return (
    <div className="flex gap-1 bg-bg-card/60 border border-border rounded-xl p-1">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => setActiveTab(t.key)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
            activeTab === t.key
              ? 'bg-accent/15 text-accent border border-accent/25'
              : 'text-text-muted hover:text-text-secondary hover:bg-bg-hover border border-transparent'
          }`}
        >
          <t.icon size={16} />
          {t.label}
        </button>
      ))}
    </div>
  )
}

function ScoreCircle({ score, size = 'lg' }) {
  const dims = size === 'lg' ? 'w-20 h-20 text-2xl' : 'w-12 h-12 text-base'
  const borderW = size === 'lg' ? 'border-[3px]' : 'border-2'
  return (
    <div className={`${dims} rounded-full ${borderW} ${scoreBgRing(score)} flex items-center justify-center`}>
      <span className={`font-bold ${scoreColor(score)}`}>
        {score != null ? score : '--'}
      </span>
    </div>
  )
}

function DynamicList({ label, items, onChange, placeholder }) {
  function addItem() {
    onChange([...items, ''])
  }
  function removeItem(idx) {
    onChange(items.filter((_, i) => i !== idx))
  }
  function updateItem(idx, val) {
    const copy = [...items]
    copy[idx] = val
    onChange(copy)
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm text-text-secondary">{label}</label>
      <div className="space-y-2">
        {items.map((item, idx) => (
          <div key={idx} className="flex gap-2">
            <input
              value={item}
              onChange={e => updateItem(idx, e.target.value)}
              placeholder={placeholder}
              className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 transition-colors"
            />
            <button
              type="button"
              onClick={() => removeItem(idx)}
              className="p-2 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
            >
              <Minus size={16} />
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={addItem}
        className="flex items-center gap-1.5 text-xs text-accent/70 hover:text-accent transition-colors mt-1 cursor-pointer"
      >
        <Plus size={14} /> Agregar
      </button>
    </div>
  )
}

// ---------- Conversation Transcript ----------

function ConversationView({ transcript }) {
  const endRef = useRef(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  if (!transcript || transcript.length === 0) {
    return <p className="text-sm text-text-muted text-center py-8">Sin transcripcion disponible</p>
  }

  return (
    <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
      {transcript.map((msg, idx) => {
        const isPersona = msg.role === 'persona'
        return (
          <div
            key={idx}
            className={`flex gap-3 ${isPersona ? 'justify-start' : 'justify-end'}`}
            style={{ animationDelay: `${idx * 50}ms` }}
          >
            {isPersona && (
              <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center flex-shrink-0 mt-1">
                <User size={14} className="text-purple-400" />
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                isPersona
                  ? 'bg-purple-500/10 border border-purple-500/20 text-text-primary rounded-tl-md'
                  : 'bg-accent/10 border border-accent/20 text-text-primary rounded-tr-md'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.timestamp && (
                <p className={`text-[10px] mt-1.5 ${isPersona ? 'text-purple-400/50' : 'text-accent/40'}`}>
                  {msg.timestamp}
                </p>
              )}
            </div>
            {!isPersona && (
              <div className="w-8 h-8 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot size={14} className="text-accent" />
              </div>
            )}
          </div>
        )
      })}
      <div ref={endRef} />
    </div>
  )
}

// ---------- Persona Card ----------

function PersonaCard({ persona, onTest, onEdit, onDelete }) {
  const isTemplate = persona.is_template
  const diff = DIFFICULTY_CONFIG[persona.difficulty] || DIFFICULTY_CONFIG.medium
  const tags = persona.tags || []

  return (
    <Card className="group hover:border-accent/30 transition-all duration-300 flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-semibold text-text-primary truncate">{persona.name}</h3>
          <DifficultyBadge difficulty={persona.difficulty} />
        </div>
        {isTemplate && (
          <span className="flex items-center gap-1 text-[11px] text-amber-400/80 bg-amber-400/10 border border-amber-400/20 px-2 py-0.5 rounded-full flex-shrink-0 ml-2">
            <Star size={11} /> Plantilla
          </span>
        )}
      </div>

      <p className="text-sm text-text-secondary line-clamp-2 mb-2 leading-relaxed">
        {persona.personality}
      </p>

      {persona.objective && (
        <p className="text-xs text-text-muted line-clamp-1 mb-3 flex items-center gap-1.5">
          <Target size={12} className="flex-shrink-0 text-accent/50" />
          {persona.objective}
        </p>
      )}

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {tags.slice(0, 4).map(tag => <TagPill key={tag} tag={tag} />)}
          {tags.length > 4 && (
            <span className="text-[11px] text-text-muted">+{tags.length - 4}</span>
          )}
        </div>
      )}

      <div className="mt-auto pt-3 border-t border-border/50 flex items-center gap-2">
        <Button
          className="flex items-center gap-1.5 text-xs !px-3 !py-1.5"
          onClick={() => onTest(persona)}
        >
          <Play size={13} /> Probar
        </Button>
        {!isTemplate && (
          <>
            <button
              onClick={() => onEdit(persona)}
              className="p-1.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
              title="Editar"
            >
              <Pencil size={14} />
            </button>
            <button
              onClick={() => onDelete(persona)}
              className="p-1.5 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
              title="Eliminar"
            >
              <Trash2 size={14} />
            </button>
          </>
        )}
      </div>
    </Card>
  )
}

// ---------- Main Component ----------

export function LoopTalk() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()

  const clientId = user?.client_id

  // Main state
  const [activeTab, setActiveTab] = useState('personas')
  const [personas, setPersonas] = useState([])
  const [runs, setRuns] = useState([])
  const [suites, setSuites] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [showRunModal, setShowRunModal] = useState(null)
  const [selectedRun, setSelectedRun] = useState(null)
  const [editingPersona, setEditingPersona] = useState(null)

  // Create/Edit form
  const emptyForm = {
    name: '',
    personality: '',
    objective: '',
    criteria: [''],
    curveballs: [],
    difficulty: 'medium',
    tags: '',
  }
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  // Generate AI form
  const [genDescription, setGenDescription] = useState('')
  const [genCount, setGenCount] = useState(5)
  const [generating, setGenerating] = useState(false)
  const [genResults, setGenResults] = useState([])
  const [addingGen, setAddingGen] = useState({})

  // Run form
  const [runAgentId, setRunAgentId] = useState('')
  const [runMaxTurns, setRunMaxTurns] = useState(20)
  const [startingRun, setStartingRun] = useState(false)

  // Suite form
  const [showSuiteModal, setShowSuiteModal] = useState(false)
  const [suiteForm, setSuiteForm] = useState({ name: '', persona_ids: [] })
  const [runningSuiteId, setRunningSuiteId] = useState(null)

  // Run detail
  const [runDetail, setRunDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // ---------- Data Loading ----------

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      api.get('/looptalk/personas'),
      api.get('/looptalk/runs'),
      api.get('/looptalk/suites'),
      clientId ? api.get(`/clients/${clientId}/agents`) : Promise.resolve([]),
    ])
      .then(([p, r, s, a]) => {
        if (cancelled) return
        setPersonas(p)
        setRuns(r)
        setSuites(s)
        setAgents(a)
      })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [clientId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Poll running tests
  useEffect(() => {
    const hasRunning = runs.some(r => r.status === 'running')
    if (!hasRunning) return
    const interval = setInterval(async () => {
      try {
        const data = await api.get('/looptalk/runs')
        setRuns(data)
      } catch { /* silently retry */ }
    }, 3000)
    return () => clearInterval(interval)
  }, [runs])

  // ---------- Persona CRUD ----------

  async function loadPersonas() {
    try {
      const data = await api.get('/looptalk/personas')
      setPersonas(data)
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function loadRuns() {
    try {
      const data = await api.get('/looptalk/runs')
      setRuns(data)
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function loadSuites() {
    try {
      const data = await api.get('/looptalk/suites')
      setSuites(data)
    } catch (err) {
      toast.error(err.message)
    }
  }

  function openCreate() {
    setEditingPersona(null)
    setForm(emptyForm)
    setShowCreateModal(true)
  }

  function openEdit(persona) {
    setEditingPersona(persona)
    setForm({
      name: persona.name || '',
      personality: persona.personality || '',
      objective: persona.objective || '',
      criteria: (persona.success_criteria || persona.criteria)?.length ? (persona.success_criteria || persona.criteria) : [''],
      curveballs: persona.curveballs?.length ? persona.curveballs : [],
      difficulty: persona.difficulty || 'medium',
      tags: (persona.tags || []).join(', '),
    })
    setShowCreateModal(true)
  }

  async function handleSavePersona() {
    if (!form.name.trim()) { toast.error('El nombre es requerido'); return }
    if (!form.personality.trim()) { toast.error('La personalidad es requerida'); return }

    setSaving(true)
    const payload = {
      name: form.name.trim(),
      personality: form.personality.trim(),
      objective: form.objective.trim(),
      success_criteria: form.criteria.filter(c => c.trim()),
      curveballs: form.curveballs.filter(c => c.trim()),
      difficulty: form.difficulty,
      tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
    }

    try {
      if (editingPersona) {
        await api.patch(`/looptalk/personas/${editingPersona.id}`, payload)
        toast.success('Persona actualizada')
      } else {
        await api.post('/looptalk/personas', payload)
        toast.success('Persona creada')
      }
      setShowCreateModal(false)
      await loadPersonas()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDeletePersona(persona) {
    const ok = await confirm({
      title: 'Eliminar persona',
      message: `Eliminar "${persona.name}"? Esta accion no se puede deshacer.`,
      type: 'danger',
      confirmLabel: 'Eliminar',
    })
    if (!ok) return
    try {
      await api.delete(`/looptalk/personas/${persona.id}`)
      toast.success('Persona eliminada')
      await loadPersonas()
    } catch (err) {
      toast.error(err.message)
    }
  }

  // ---------- AI Generate ----------

  async function handleGenerate() {
    if (!genDescription.trim()) { toast.error('Describe tu negocio'); return }
    setGenerating(true)
    setGenResults([])
    try {
      const data = await api.post('/looptalk/personas/generate', {
        description: genDescription.trim(),
        count: genCount,
      })
      setGenResults(data.personas || data || [])
    } catch (err) {
      toast.error(err.message)
    } finally {
      setGenerating(false)
    }
  }

  async function handleAddGenerated(persona, idx) {
    setAddingGen(prev => ({ ...prev, [idx]: true }))
    try {
      await api.post('/looptalk/personas', persona)
      toast.success(`"${persona.name}" agregada`)
      await loadPersonas()
      setGenResults(prev => prev.filter((_, i) => i !== idx))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setAddingGen(prev => ({ ...prev, [idx]: false }))
    }
  }

  // ---------- Run Test ----------

  async function handleStartRun() {
    if (!runAgentId) { toast.error('Selecciona un agente'); return }
    setStartingRun(true)
    try {
      await api.post('/looptalk/run', {
        agent_id: runAgentId,
        persona_id: showRunModal.id,
        max_turns: runMaxTurns,
      })
      toast.success('Prueba iniciada')
      setShowRunModal(null)
      setActiveTab('resultados')
      await loadRuns()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setStartingRun(false)
    }
  }

  async function handleViewRunDetail(run) {
    setSelectedRun(run)
    setLoadingDetail(true)
    try {
      const data = await api.get(`/looptalk/runs/${run.id}`)
      setRunDetail(data)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoadingDetail(false)
    }
  }

  async function handleDeleteRun(run) {
    const ok = await confirm({
      title: 'Eliminar resultado',
      message: 'Eliminar este resultado de prueba?',
      type: 'danger',
      confirmLabel: 'Eliminar',
    })
    if (!ok) return
    try {
      await api.delete(`/looptalk/runs/${run.id}`)
      toast.success('Resultado eliminado')
      await loadRuns()
    } catch (err) {
      toast.error(err.message)
    }
  }

  // ---------- Suites ----------

  async function handleRunSuite(suite) {
    if (!agents.length) { toast.error('No hay agentes disponibles'); return }
    setRunningSuiteId(suite.id)
    try {
      await api.post(`/looptalk/suites/${suite.id}/run`, { agent_id: agents[0]?.id })
      toast.success('Suite iniciada')
      setActiveTab('resultados')
      await loadRuns()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setRunningSuiteId(null)
    }
  }

  async function handleCreateSuite() {
    if (!suiteForm.name.trim()) { toast.error('Nombre requerido'); return }
    try {
      await api.post('/looptalk/suites', {
        name: suiteForm.name.trim(),
        persona_ids: suiteForm.persona_ids,
      })
      toast.success('Suite creada')
      setShowSuiteModal(false)
      setSuiteForm({ name: '', persona_ids: [] })
      await loadSuites()
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDeleteSuite(suite) {
    const ok = await confirm({
      title: 'Eliminar suite',
      message: `Eliminar "${suite.name}"?`,
      type: 'danger',
      confirmLabel: 'Eliminar',
    })
    if (!ok) return
    try {
      await api.delete(`/looptalk/suites/${suite.id}`)
      toast.success('Suite eliminada')
      await loadSuites()
    } catch (err) {
      toast.error(err.message)
    }
  }

  // ---------- Render ----------

  if (loading) return <PageLoader />

  // Run detail view
  if (selectedRun) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => { setSelectedRun(null); setRunDetail(null) }}
          className="flex items-center gap-2 text-sm text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        >
          <ArrowLeft size={16} /> Volver a resultados
        </button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Detalle de Prueba</h1>
            <p className="text-sm text-text-muted mt-1">
              {selectedRun.persona_name} vs {selectedRun.agent_name}
            </p>
          </div>
          <StatusDot status={selectedRun.status} />
        </div>

        {loadingDetail ? (
          <PageLoader />
        ) : runDetail ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Conversation */}
            <div className="lg:col-span-2">
              <Card className="h-full">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2">
                  <MessageSquare size={16} className="text-accent/60" />
                  Conversacion
                </h3>
                <ConversationView transcript={runDetail.transcript || []} />
              </Card>
            </div>

            {/* Evaluation Panel */}
            <div className="space-y-4">
              {/* Score */}
              <Card className="flex flex-col items-center py-6">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-3">Puntaje General</p>
                <ScoreCircle score={runDetail.evaluation?.score} size="lg" />
                <div className="flex items-center gap-4 mt-4 text-xs text-text-muted">
                  <span className="flex items-center gap-1">
                    <MessageSquare size={12} /> {runDetail.turn_count || '--'} turnos
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {formatDuration(runDetail.duration_seconds)}
                  </span>
                </div>
              </Card>

              {/* Criteria */}
              {runDetail.evaluation?.criteria && (
                <Card>
                  <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
                    <ListChecks size={16} className="text-accent/60" />
                    Criterios
                  </h3>
                  <div className="space-y-2.5">
                    {runDetail.evaluation.criteria.map((c, idx) => (
                      <div key={idx} className="flex items-start gap-2.5">
                        {c.passed ? (
                          <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                        ) : (
                          <XCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                        )}
                        <div>
                          <p className="text-sm text-text-primary">{c.name}</p>
                          {c.explanation && (
                            <p className="text-xs text-text-muted mt-0.5">{c.explanation}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Summary */}
              {runDetail.evaluation?.summary && (
                <Card>
                  <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Target size={16} className="text-accent/60" />
                    Resumen
                  </h3>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {runDetail.evaluation.summary}
                  </p>
                </Card>
              )}

              {/* Suggestions */}
              {runDetail.evaluation?.suggestions?.length > 0 && (
                <Card>
                  <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Lightbulb size={16} className="text-amber-400/60" />
                    Sugerencias
                  </h3>
                  <ul className="space-y-2">
                    {runDetail.evaluation.suggestions.map((s, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-text-secondary">
                        <ChevronRight size={14} className="text-accent/40 flex-shrink-0 mt-0.5" />
                        {s}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          </div>
        ) : (
          <Card>
            <p className="text-sm text-text-muted text-center py-8">No se pudo cargar el detalle</p>
          </Card>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent/20 to-purple-500/20 border border-accent/20 flex items-center justify-center">
              <FlaskConical size={20} className="text-accent" />
            </div>
            LoopTalk &mdash; Test Personas
          </h1>
          <p className="text-sm text-text-muted mt-1.5 ml-[52px]">
            Pruebas automatizadas con IA para tus agentes de voz
          </p>
        </div>
        <div className="flex items-center gap-2 ml-[52px] sm:ml-0">
          <Button variant="secondary" onClick={() => setShowGenerateModal(true)} className="flex items-center gap-1.5">
            <Sparkles size={15} /> Generar con IA
          </Button>
          <Button onClick={openCreate} className="flex items-center gap-1.5">
            <Plus size={15} /> Nueva Persona
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <TabNav activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Personas Tab */}
      {activeTab === 'personas' && (
        personas.length === 0 ? (
          <Card>
            <EmptyState
              icon={Users}
              title="Sin personas de prueba"
              description="Crea tu primera persona de prueba o genera varias con IA para evaluar tus agentes."
              action={openCreate}
              actionLabel="Nueva Persona"
              actionIcon={Plus}
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {personas.map(p => (
              <PersonaCard
                key={p.id}
                persona={p}
                onTest={persona => {
                  setShowRunModal(persona)
                  setRunAgentId(agents[0]?.id || '')
                  setRunMaxTurns(20)
                }}
                onEdit={openEdit}
                onDelete={handleDeletePersona}
              />
            ))}
          </div>
        )
      )}

      {/* Resultados Tab */}
      {activeTab === 'resultados' && (
        runs.length === 0 ? (
          <Card>
            <EmptyState
              icon={BarChart3}
              title="Sin resultados"
              description="Ejecuta una prueba con una persona para ver los resultados aqui."
              action={() => setActiveTab('personas')}
              actionLabel="Ir a Personas"
              actionIcon={Play}
            />
          </Card>
        ) : (
          <Card className="overflow-hidden !p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Estado</th>
                    <th className="text-left text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Persona</th>
                    <th className="text-left text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Agente</th>
                    <th className="text-center text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Puntaje</th>
                    <th className="text-center text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Turnos</th>
                    <th className="text-center text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Duracion</th>
                    <th className="text-left text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3">Fecha</th>
                    <th className="text-right text-xs font-medium text-text-muted uppercase tracking-wider px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {runs.map(run => (
                    <tr key={run.id} className="hover:bg-bg-hover/50 transition-colors">
                      <td className="px-5 py-3.5">
                        <StatusDot status={run.status} />
                      </td>
                      <td className="px-5 py-3.5 text-sm text-text-primary font-medium">
                        {run.persona_name || '--'}
                      </td>
                      <td className="px-5 py-3.5 text-sm text-text-secondary">
                        {run.agent_name || '--'}
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <span className={`text-lg font-bold ${scoreColor(run.score)}`}>
                          {run.score != null ? run.score : '--'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-center text-sm text-text-muted">
                        {run.turn_count || '--'}
                      </td>
                      <td className="px-5 py-3.5 text-center text-sm text-text-muted">
                        {formatDuration(run.duration_seconds)}
                      </td>
                      <td className="px-5 py-3.5 text-sm text-text-muted">
                        {formatDate(run.created_at)}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {run.status === 'completed' && (
                            <button
                              onClick={() => handleViewRunDetail(run)}
                              className="text-xs text-accent hover:text-accent/80 transition-colors px-2 py-1 rounded cursor-pointer"
                            >
                              Ver Detalle
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteRun(run)}
                            className="p-1.5 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      )}

      {/* Suites Tab */}
      {activeTab === 'suites' && (
        <>
          <div className="flex justify-end mb-2">
            <Button onClick={() => setShowSuiteModal(true)} className="flex items-center gap-1.5">
              <Plus size={15} /> Nueva Suite
            </Button>
          </div>
          {suites.length === 0 ? (
            <Card>
              <EmptyState
                icon={FolderOpen}
                title="Sin suites"
                description="Agrupa personas en suites para ejecutar multiples pruebas a la vez."
                action={() => setShowSuiteModal(true)}
                actionLabel="Nueva Suite"
                actionIcon={Plus}
              />
            </Card>
          ) : (
            <div className="space-y-3">
              {suites.map(suite => (
                <Card key={suite.id} className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-text-primary">{suite.name}</h3>
                    <p className="text-xs text-text-muted mt-0.5">
                      {suite.persona_count ?? suite.persona_ids?.length ?? 0} personas
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => handleRunSuite(suite)}
                      disabled={runningSuiteId === suite.id}
                      className="flex items-center gap-1.5 text-xs !px-3 !py-1.5"
                    >
                      {runningSuiteId === suite.id ? <Spinner size={14} /> : <Play size={13} />}
                      Correr Todo
                    </Button>
                    <button
                      onClick={() => handleDeleteSuite(suite)}
                      className="p-1.5 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {/* ---------- Modals ---------- */}

      {/* Create/Edit Persona Modal */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={editingPersona ? 'Editar Persona' : 'Nueva Persona'}
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4">
          <Input
            label="Nombre"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Ej: Cliente impaciente con dudas de precio"
          />
          <Textarea
            label="Personalidad"
            value={form.personality}
            onChange={e => setForm(f => ({ ...f, personality: e.target.value }))}
            placeholder="Describe como habla esta persona, su tono, nivel de paciencia, vocabulario..."
            className="!min-h-[120px]"
          />
          <Textarea
            label="Objetivo"
            value={form.objective}
            onChange={e => setForm(f => ({ ...f, objective: e.target.value }))}
            placeholder="Que quiere lograr esta persona en la llamada?"
          />
          <DynamicList
            label="Criterios de exito"
            items={form.criteria}
            onChange={criteria => setForm(f => ({ ...f, criteria }))}
            placeholder="Ej: El agente resuelve la duda de precio"
          />
          <DynamicList
            label="Sorpresas / Curveballs"
            items={form.curveballs}
            onChange={curveballs => setForm(f => ({ ...f, curveballs }))}
            placeholder="Ej: Cambia de tema abruptamente"
          />
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Dificultad"
              options={DIFFICULTY_OPTIONS}
              value={form.difficulty}
              onChange={e => setForm(f => ({ ...f, difficulty: e.target.value }))}
            />
            <Input
              label="Tags (separados por coma)"
              value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
              placeholder="precio, impaciente, nuevo"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSavePersona} disabled={saving} className="flex items-center gap-1.5">
              {saving && <Spinner size={14} />}
              {editingPersona ? 'Guardar Cambios' : 'Crear Persona'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* AI Generate Modal */}
      <Modal
        open={showGenerateModal}
        onClose={() => { setShowGenerateModal(false); setGenResults([]) }}
        title="Generar Personas con IA"
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4">
          {genResults.length === 0 ? (
            <>
              <Textarea
                label="Describe tu negocio y el tipo de clientes que recibes"
                value={genDescription}
                onChange={e => setGenDescription(e.target.value)}
                placeholder="Ej: Somos una clinica dental en Merida. Recibimos llamadas de pacientes nuevos preguntando por precios, pacientes existentes reagendando citas, y urgencias dentales..."
                className="!min-h-[120px]"
              />
              <Input
                label="Cantidad de personas a generar"
                type="number"
                min={1}
                max={20}
                value={genCount}
                onChange={e => setGenCount(parseInt(e.target.value) || 5)}
              />
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setShowGenerateModal(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleGenerate} disabled={generating} className="flex items-center gap-1.5">
                  {generating ? <Spinner size={14} /> : <Sparkles size={15} />}
                  {generating ? 'Generando...' : 'Generar'}
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-text-secondary">
                {genResults.length} personas generadas. Agrega las que desees:
              </p>
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                {genResults.map((persona, idx) => (
                  <Card key={idx} className="!p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-text-primary text-sm">{persona.name}</h4>
                          <DifficultyBadge difficulty={persona.difficulty} />
                        </div>
                        <p className="text-xs text-text-secondary line-clamp-2">{persona.personality}</p>
                        {persona.objective && (
                          <p className="text-xs text-text-muted mt-1 flex items-center gap-1">
                            <Target size={10} /> {persona.objective}
                          </p>
                        )}
                      </div>
                      <Button
                        onClick={() => handleAddGenerated(persona, idx)}
                        disabled={addingGen[idx]}
                        className="flex items-center gap-1 text-xs !px-3 !py-1.5 flex-shrink-0"
                      >
                        {addingGen[idx] ? <Spinner size={12} /> : <Plus size={13} />}
                        Agregar
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
              <div className="flex justify-between pt-2">
                <Button variant="secondary" onClick={() => setGenResults([])}>
                  <ArrowLeft size={14} className="mr-1.5" /> Volver
                </Button>
                <Button variant="secondary" onClick={() => { setShowGenerateModal(false); setGenResults([]) }}>
                  Cerrar
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Run Agent Selection Modal */}
      <Modal
        open={!!showRunModal}
        onClose={() => setShowRunModal(null)}
        title="Iniciar Prueba"
        maxWidth="max-w-md"
      >
        {showRunModal && (
          <div className="space-y-4">
            <div className="bg-bg-secondary/50 border border-border rounded-lg p-3">
              <p className="text-xs text-text-muted">Persona</p>
              <p className="text-sm font-medium text-text-primary mt-0.5">{showRunModal.name}</p>
            </div>

            {agents.length === 0 ? (
              <p className="text-sm text-text-muted text-center py-4">
                No hay agentes disponibles. Crea un agente primero.
              </p>
            ) : (
              <>
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm text-text-secondary">Selecciona un agente</label>
                  <div className="space-y-2">
                    {agents.map(agent => (
                      <button
                        key={agent.id}
                        onClick={() => setRunAgentId(agent.id)}
                        className={`w-full text-left px-4 py-3 rounded-lg border transition-all cursor-pointer ${
                          runAgentId === agent.id
                            ? 'border-accent/50 bg-accent/10 text-text-primary'
                            : 'border-border bg-bg-secondary hover:border-border/80 text-text-secondary'
                        }`}
                      >
                        <p className="text-sm font-medium">{agent.name}</p>
                        {agent.agent_type && (
                          <p className="text-xs text-text-muted mt-0.5">{agent.agent_type}</p>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-sm text-text-secondary">
                    Turnos maximos: <span className="text-accent font-medium">{runMaxTurns}</span>
                  </label>
                  <input
                    type="range"
                    min={5}
                    max={30}
                    value={runMaxTurns}
                    onChange={e => setRunMaxTurns(parseInt(e.target.value))}
                    className="w-full accent-[#00f0ff]"
                  />
                  <div className="flex justify-between text-[10px] text-text-muted">
                    <span>5</span>
                    <span>30</span>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" onClick={() => setShowRunModal(null)}>
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleStartRun}
                    disabled={startingRun || !runAgentId}
                    className="flex items-center gap-1.5"
                  >
                    {startingRun ? <Spinner size={14} /> : <Play size={15} />}
                    Iniciar Prueba
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </Modal>

      {/* Create Suite Modal */}
      <Modal
        open={showSuiteModal}
        onClose={() => setShowSuiteModal(false)}
        title="Nueva Suite"
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <Input
            label="Nombre de la suite"
            value={suiteForm.name}
            onChange={e => setSuiteForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Ej: Pruebas de precio"
          />
          {personas.filter(p => !p.is_template).length > 0 && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-text-secondary">Selecciona personas</label>
              <div className="space-y-1.5 max-h-[250px] overflow-y-auto">
                {personas.filter(p => !p.is_template).map(p => (
                  <label
                    key={p.id}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                      suiteForm.persona_ids.includes(p.id)
                        ? 'border-accent/40 bg-accent/5'
                        : 'border-border hover:border-border/80'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={suiteForm.persona_ids.includes(p.id)}
                      onChange={e => {
                        setSuiteForm(f => ({
                          ...f,
                          persona_ids: e.target.checked
                            ? [...f.persona_ids, p.id]
                            : f.persona_ids.filter(id => id !== p.id),
                        }))
                      }}
                      className="accent-[#00f0ff]"
                    />
                    <span className="text-sm text-text-primary">{p.name}</span>
                    <DifficultyBadge difficulty={p.difficulty} />
                  </label>
                ))}
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowSuiteModal(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateSuite} className="flex items-center gap-1.5">
              <Plus size={15} /> Crear Suite
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
