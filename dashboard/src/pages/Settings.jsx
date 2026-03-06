import { useEffect, useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Save, Volume2, Zap, RefreshCw, Eye, FileText, Bot, Plus, Trash2, Mic,
  Brain, Key, ChevronDown, ChevronUp, Check, Phone, MessageCircle, Settings2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader, Spinner } from '../components/ui/Spinner'
import { PromptAssistant } from '../components/PromptAssistant'
import { ChatTesterButton } from '../components/ChatTester'
import { WhatsAppConfig } from '../components/WhatsAppConfig'

/* ─────────────────────────── Constants ─────────────────────────── */

const STT_OPTIONS = [
  { value: 'deepgram', label: 'Deepgram Nova-3', included: true },
  { value: 'google', label: 'Google STT', included: false },
  { value: 'openai', label: 'OpenAI Whisper', included: false },
]

const LLM_OPTIONS = [
  { value: 'google', label: 'Gemini 2.5 Flash', included: true },
  { value: 'openai', label: 'OpenAI GPT-4o', included: false },
  { value: 'anthropic', label: 'Anthropic Claude', included: false },
]

const TTS_OPTIONS = [
  { value: 'cartesia', label: 'Cartesia Sonic 3', included: true },
  { value: 'elevenlabs', label: 'ElevenLabs', included: false },
  { value: 'openai', label: 'OpenAI TTS', included: false },
]

const REALTIME_VOICES = [
  { value: 'alloy', label: 'Alloy', desc: 'Neutral, balanceada' },
  { value: 'ash', label: 'Ash', desc: 'Clara, precisa' },
  { value: 'ballad', label: 'Ballad', desc: 'Melodica, suave' },
  { value: 'coral', label: 'Coral', desc: 'Calida, amigable' },
  { value: 'echo', label: 'Echo', desc: 'Resonante, profunda' },
  { value: 'sage', label: 'Sage', desc: 'Calmada, reflexiva' },
  { value: 'shimmer', label: 'Shimmer', desc: 'Brillante, energetica' },
  { value: 'verse', label: 'Verse', desc: 'Versatil, expresiva' },
  { value: 'marin', label: 'Marin', desc: 'Nueva, alta calidad (recomendada)' },
  { value: 'cedar', label: 'Cedar', desc: 'Nueva, alta calidad (recomendada)' },
]

const REALTIME_MODELS = [
  { value: 'gpt-4o-realtime-preview', label: 'gpt-4o-realtime-preview' },
  { value: 'gpt-4o-mini-realtime-preview', label: 'gpt-4o-mini-realtime-preview' },
]

const PROVIDER_LABELS = {
  cartesia: 'Cartesia',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI TTS',
}

const TABS = [
  { key: 'general', label: 'General', icon: Bot },
  { key: 'voice', label: 'Voz', icon: Volume2 },
  { key: 'calls', label: 'Llamadas', icon: Phone },
  { key: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { key: 'advanced', label: 'Avanzado', icon: Settings2 },
]

/* ─────────────────────── Helper Components ──────────────────────── */

function PipelineSelect({ label, value, onChange, options, icon: Icon }) {
  return (
    <div>
      {label && <label className="block text-xs text-text-muted mb-1">{label}</label>}
      <div className="relative">
        {Icon && (
          <Icon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        )}
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className={`w-full bg-bg-primary border border-border rounded-lg py-2 pr-8 text-sm text-text-primary appearance-none focus:outline-none focus:border-accent transition-colors ${Icon ? 'pl-9' : 'pl-3'}`}
        >
          {options.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
      </div>
    </div>
  )
}

function ApiKeyField({ label, hasKey, value, onChange, onClear }) {
  const [editing, setEditing] = useState(false)

  if (hasKey && !editing) {
    return (
      <div>
        <label className="block text-xs text-text-muted mb-1">{label}</label>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-sm flex-1">
            <Check size={14} className="text-success" />
            <span className="text-success">Configurada</span>
          </div>
          <Button variant="secondary" onClick={() => setEditing(true)} className="text-xs px-3">
            Cambiar
          </Button>
          <Button
            variant="secondary"
            onClick={() => { onClear(); setEditing(false) }}
            className="text-xs px-3 text-red-400 hover:text-red-300"
          >
            Quitar
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1">{label}</label>
      <Input
        type="password"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="sk-..."
      />
    </div>
  )
}

function CostEstimator({ sttProvider, llmProvider, ttsProvider }) {
  const [estimate, setEstimate] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchEstimate = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.post('/costs/estimate', {
        stt_provider: sttProvider,
        llm_provider: llmProvider,
        tts_provider: ttsProvider,
        minutes: 1,
      })
      setEstimate(data)
    } catch {
      setEstimate(null)
    } finally {
      setLoading(false)
    }
  }, [sttProvider, llmProvider, ttsProvider])

  useEffect(() => {
    fetchEstimate()
  }, [fetchEstimate])

  if (loading || !estimate) return null

  return (
    <div className="p-4 rounded-lg border border-border bg-bg-secondary/50">
      <h3 className="text-xs font-semibold text-text-secondary mb-2">Estimacion de costos (por minuto)</h3>
      <div className="space-y-1.5 text-sm font-mono">
        {estimate.lines.map((line, i) => (
          <div key={i} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-text-muted text-xs truncate">{line.label}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                line.classification === 'platform'
                  ? 'bg-accent/15 text-accent'
                  : 'bg-bg-hover text-text-muted'
              }`}>
                {line.classification === 'platform' ? 'Plataforma' : 'Externo'}
              </span>
            </div>
            <span className={`text-xs ${line.is_estimate ? 'text-text-muted' : ''}`}>
              {line.is_estimate ? '~' : ''}${line.amount.toFixed(4)}
            </span>
          </div>
        ))}
        <div className="border-t border-border pt-1.5 flex justify-between text-xs">
          <span className="text-accent font-semibold font-sans">Plataforma</span>
          <span className="text-accent font-semibold">${estimate.platform_cost.toFixed(4)}/min</span>
        </div>
        {estimate.external_cost_estimate > 0 && (
          <div className="flex justify-between text-xs text-text-muted">
            <span className="font-sans">APIs externas (est.)</span>
            <span>~${estimate.external_cost_estimate.toFixed(4)}/min</span>
          </div>
        )}
      </div>
      {estimate.external_cost_estimate > 0 && (
        <p className="text-[10px] text-text-muted mt-2 font-sans">
          Los costos de APIs externas son estimados y pueden variar.
        </p>
      )}
    </div>
  )
}

/* ─────────────────────── Main Component ─────────────────────────── */

export function Settings() {
  const { agentId: urlAgentId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  /* ── State ── */
  const [client, setClient] = useState(null)
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [voices, setVoices] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('general')
  const [showPreview, setShowPreview] = useState(false)
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [newAgentForm, setNewAgentForm] = useState({ name: '', agent_type: 'inbound', role_description: '' })
  const [creatingAgent, setCreatingAgent] = useState(false)

  // Comprehensive form state
  const [form, setForm] = useState({
    name: '', agent_type: 'inbound', greeting: '', system_prompt: '', examples: '',
    after_hours_message: '', conversation_mode: 'prompt', max_call_duration_seconds: 300,
    transfer_number: '', is_active: true,
    agent_mode: 'pipeline', stt_provider: 'deepgram', llm_provider: 'google', tts_provider: 'cartesia',
    stt_api_key: '', llm_api_key: '', tts_api_key: '', realtime_api_key: '',
    realtime_voice: 'alloy', realtime_model: 'gpt-4o-realtime-preview', voice_id: '',
    role_description: '', orchestrator_enabled: true, orchestrator_priority: 0,
  })

  // Track server-side API key existence
  const [serverKeys, setServerKeys] = useState({
    has_stt_api_key: false,
    has_llm_api_key: false,
    has_tts_api_key: false,
    has_realtime_api_key: false,
  })

  const clientId = client?.id || user?.client_id

  /* ── Populate form from agent data ── */
  function populateForm(agentData) {
    const vc = agentData.voice_config || {}
    const lc = agentData.llm_config || {}
    const sc = agentData.stt_config || {}
    setForm({
      name: agentData.name || '',
      agent_type: agentData.agent_type || 'inbound',
      greeting: agentData.greeting || '',
      system_prompt: agentData.system_prompt || '',
      examples: agentData.examples || '',
      after_hours_message: agentData.after_hours_message || '',
      conversation_mode: agentData.conversation_mode || 'prompt',
      max_call_duration_seconds: agentData.max_call_duration_seconds || 300,
      transfer_number: agentData.transfer_number || '',
      is_active: agentData.is_active !== false,
      agent_mode: agentData.agent_mode || 'pipeline',
      stt_provider: sc.provider || 'deepgram',
      llm_provider: lc.provider || 'google',
      tts_provider: vc.provider || 'cartesia',
      stt_api_key: '', llm_api_key: '', tts_api_key: '', realtime_api_key: '',
      realtime_voice: vc.realtime_voice || 'alloy',
      realtime_model: vc.realtime_model || 'gpt-4o-realtime-preview',
      voice_id: vc.voice_id || '',
      role_description: agentData.role_description || '',
      orchestrator_enabled: agentData.orchestrator_enabled !== false,
      orchestrator_priority: agentData.orchestrator_priority || 0,
    })
    setServerKeys({
      has_stt_api_key: sc.has_api_key || false,
      has_llm_api_key: lc.has_api_key || false,
      has_tts_api_key: vc.has_api_key || false,
      has_realtime_api_key: vc.has_realtime_api_key || false,
    })
  }

  /* ── Voice loading ── */
  async function loadVoicesForAgent(agentData, cid) {
    const vc = agentData?.voice_config || {}
    const provider = vc.provider || 'cartesia'
    const mode = agentData?.agent_mode || 'pipeline'

    if (mode === 'realtime') {
      setVoices([])
      return
    }

    setLoadingVoices(true)
    try {
      if (provider === 'elevenlabs' || provider === 'openai') {
        const v = await api.get(`/voices/provider/${cid}?agent_id=${agentData.id}`)
        setVoices(v)
      } else {
        const v = await api.get('/voices')
        setVoices(v)
      }
    } catch (err) {
      console.error('Error cargando voces:', err)
      try {
        const v = await api.get('/voices')
        setVoices(v)
      } catch { /* ignore */ }
    } finally {
      setLoadingVoices(false)
    }
  }

  /* ── Select an agent ── */
  function selectAgent(agent, cid) {
    setSelectedAgent(agent)
    populateForm(agent)
    loadVoicesForAgent(agent, cid)
  }

  /* ── Initial data load ── */
  useEffect(() => {
    if (user?.role === 'admin') return setLoading(false)
    if (!user?.client_id) return setLoading(false)

    const cid = user.client_id
    Promise.all([
      api.get(`/clients/${cid}`),
      api.get(`/clients/${cid}/agents`),
      api.get('/clients/templates').catch(() => []),
    ])
      .then(([c, ag, tpls]) => {
        setClient(c)
        setAgents(ag)
        setTemplates(tpls)
        // Auto-select agent: from URL param or first
        const target = urlAgentId ? ag.find(a => a.id === urlAgentId) : ag[0]
        if (target) {
          selectAgent(target, cid)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [user]) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Refresh voices ── */
  async function handleRefreshVoices() {
    if (!selectedAgent || !clientId) return
    await loadVoicesForAgent(selectedAgent, clientId)
    toast.success('Voces actualizadas')
  }

  /* ── Handle agent selection from pills ── */
  function handleSelectAgent(agent) {
    selectAgent(agent, clientId)
  }

  /* ── Create agent ── */
  async function handleCreateAgent(e) {
    e.preventDefault()
    if (!newAgentForm.name || !clientId) return
    setCreatingAgent(true)
    try {
      const created = await api.post(`/clients/${clientId}/agents`, {
        name: newAgentForm.name,
        agent_type: newAgentForm.agent_type,
        role_description: newAgentForm.role_description || null,
      })
      setAgents(prev => [...prev, created])
      selectAgent(created, clientId)
      setShowCreateAgent(false)
      setNewAgentForm({ name: '', agent_type: 'inbound', role_description: '' })
      toast.success(`Agente "${created.name}" creado`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreatingAgent(false)
    }
  }

  /* ── Save agent (full save) ── */
  async function handleSave() {
    if (!selectedAgent || !clientId) return
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        system_prompt: form.system_prompt,
        greeting: form.greeting,
        examples: form.examples || null,
        agent_mode: form.agent_mode,
        agent_type: form.agent_type,
        transfer_number: form.transfer_number || null,
        after_hours_message: form.after_hours_message || null,
        max_call_duration_seconds: form.max_call_duration_seconds,
        is_active: form.is_active,
        voice_id: form.voice_id || null,
        stt_provider: form.stt_provider,
        llm_provider: form.llm_provider,
        tts_provider: form.tts_provider,
        realtime_voice: form.realtime_voice,
        realtime_model: form.realtime_model,
        role_description: form.role_description || null,
        orchestrator_enabled: form.orchestrator_enabled,
        orchestrator_priority: form.orchestrator_priority,
        conversation_mode: form.conversation_mode,
      }

      // Solo enviar API keys si se escribieron nuevas
      if (form.stt_api_key) payload.stt_api_key = form.stt_api_key
      if (form.llm_api_key) payload.llm_api_key = form.llm_api_key
      if (form.tts_api_key) payload.tts_api_key = form.tts_api_key
      if (form.realtime_api_key) payload.realtime_api_key = form.realtime_api_key

      const updated = await api.patch(`/clients/${clientId}/agents/${selectedAgent.id}`, payload)

      // Actualizar lista de agentes y agente seleccionado
      setAgents(prev => prev.map(a => a.id === updated.id ? updated : a))
      setSelectedAgent(updated)

      // Actualizar server keys
      const vc = updated.voice_config || {}
      const lc = updated.llm_config || {}
      const sc = updated.stt_config || {}
      setServerKeys({
        has_stt_api_key: sc.has_api_key || false,
        has_llm_api_key: lc.has_api_key || false,
        has_tts_api_key: vc.has_api_key || false,
        has_realtime_api_key: vc.has_realtime_api_key || false,
      })

      // Limpiar keys del form
      setForm(f => ({ ...f, stt_api_key: '', llm_api_key: '', tts_api_key: '', realtime_api_key: '' }))

      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  /* ── Delete agent ── */
  async function handleDelete() {
    if (!selectedAgent || !clientId) return
    const ok = await confirm({
      title: 'Eliminar agente',
      message: `Eliminar "${selectedAgent.name}"? Esta accion no se puede deshacer.`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${clientId}/agents/${selectedAgent.id}`)
      const remaining = agents.filter(a => a.id !== selectedAgent.id)
      setAgents(remaining)
      if (remaining.length > 0) {
        selectAgent(remaining[0], clientId)
      } else {
        setSelectedAgent(null)
      }
      toast.success('Agente eliminado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  /* ── API key helpers ── */
  function clearApiKey(field, serverField) {
    setForm(f => ({ ...f, [field]: '' }))
    setServerKeys(s => ({ ...s, [serverField]: false }))
  }

  function needsKey(type) {
    const opt = {
      stt: STT_OPTIONS, llm: LLM_OPTIONS, tts: TTS_OPTIONS,
    }[type]?.find(o => o.value === form[`${type}_provider`])
    return opt && !opt.included
  }

  /* ── Voices filtered and grouped ── */
  const filteredVoices = useMemo(() => {
    if (!voices?.length) return []
    if (form.tts_provider !== 'cartesia') return voices
    if (client?.language === 'es-en') return voices
    return voices.filter(v => v.language === client?.language)
  }, [voices, form.tts_provider, client?.language])

  const groupedVoices = useMemo(() => {
    const groups = {}
    for (const v of filteredVoices) {
      let key
      if (form.tts_provider === 'cartesia') {
        const lang = v.language === 'es' ? 'Espanol' : 'English'
        const gender = v.gender === 'female' ? 'Mujeres' : 'Hombres'
        key = client?.language === 'es-en' ? `${lang} — ${gender}` : gender
      } else {
        const g = v.gender || 'unknown'
        key = g === 'female' ? 'Mujeres' : g === 'male' ? 'Hombres' : 'Voces'
      }
      if (!groups[key]) groups[key] = []
      groups[key].push(v)
    }
    return groups
  }, [filteredVoices, form.tts_provider, client?.language])

  const currentVoice = voices?.find(v => v.id === form.voice_id)

  const isPipeline = form.agent_mode === 'pipeline'

  /* ─────────────────────── Render: Loading ─────────────────────── */

  if (loading) return <PageLoader />

  /* ─────────────────────── Render: Admin redirect ──────────────── */

  if (user?.role === 'admin') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Bot size={24} /> Agentes</h1>
        <Card className="space-y-4">
          <p className="text-text-secondary">
            Como administrador, configura cada cliente desde la seccion de clientes.
          </p>
          <Button onClick={() => navigate('/admin/clients')}>
            Ir a Clientes
          </Button>
        </Card>
      </div>
    )
  }

  /* ─────────────────────── Render: No client ───────────────────── */

  if (!client) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bot size={24} /> Agentes
        </h1>
        <Card>
          <p className="text-text-muted">No se encontro configuracion de cliente.</p>
        </Card>
      </div>
    )
  }

  /* ─────────────────────── Render: Main page ───────────────────── */

  return (
    <div className="space-y-6">

      {/* ── Top Section: Title + Agent selector ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Bot size={24} /> Agentes
        </h1>
        <Button variant="secondary" onClick={() => setShowCreateAgent(true)} className="text-sm">
          <Plus size={15} className="mr-1.5 inline" /> Nuevo agente
        </Button>
      </div>

      {/* Agent selector pills */}
      <div className="flex flex-wrap gap-2">
        {agents.map(agent => (
          <button
            key={agent.id}
            onClick={() => handleSelectAgent(agent)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              selectedAgent?.id === agent.id
                ? 'bg-accent/20 text-accent border border-accent/50'
                : 'bg-bg-secondary text-text-secondary border border-border hover:bg-bg-hover'
            }`}
          >
            {agent.name}
            {agent.phone_number && (
              <span className="ml-2 text-xs text-text-muted font-mono">{agent.phone_number}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Modo Inteligente toggle (when 2+ agents) ── */}
      {agents.length >= 2 && (
        <Card className="space-y-3">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-purple-400" />
            <h2 className="text-sm font-semibold text-text-secondary">Modo Inteligente</h2>
            {client.orchestration_mode === 'intelligent' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-medium">Activo</span>
            )}
          </div>
          <p className="text-xs text-text-muted">
            Permite que todos tus agentes esten disponibles en el mismo telefono.
            Un coordinador IA decide cual responde.
          </p>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={client.orchestration_mode === 'intelligent'}
              onChange={async (e) => {
                const mode = e.target.checked ? 'intelligent' : 'simple'
                try {
                  const updated = await api.patch(`/clients/${client.id}`, { orchestration_mode: mode })
                  setClient(updated)
                  toast.success(mode === 'intelligent' ? 'Modo Inteligente activado' : 'Modo Inteligente desactivado')
                } catch (err) {
                  toast.error(err.message)
                }
              }}
              className="accent-purple-400 w-4 h-4"
            />
            <span className="text-sm">Activar orquestacion multi-agente</span>
          </label>
          {client.orchestration_mode === 'intelligent' && (
            <div className="space-y-1.5 pl-7">
              {agents.map(agent => (
                <div key={agent.id} className="flex items-center gap-2 text-xs text-text-secondary">
                  <span className="w-2 h-2 rounded-full bg-purple-400" />
                  <span className="font-medium">{agent.name}</span>
                  <span className="text-text-muted truncate">{agent.role_description || 'Sin rol definido'}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ── Tab content (only when agent selected) ── */}
      {selectedAgent && (
        <>
          {/* Tab navigation */}
          <div className="flex border-b border-border">
            {TABS.map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors cursor-pointer ${
                    activeTab === tab.key
                      ? 'border-accent text-accent'
                      : 'border-transparent text-text-muted hover:text-text-primary'
                  }`}
                >
                  <Icon size={15} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Tab panels */}
          <div className="min-h-[400px]">

            {/* ── General Tab ── */}
            {activeTab === 'general' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left column: Agent config */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary">Agente</h2>

                  <Input
                    label="Nombre del agente"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  />

                  <Select
                    label="Tipo"
                    value={form.agent_type}
                    onChange={e => setForm(f => ({ ...f, agent_type: e.target.value }))}
                    options={[
                      { value: 'inbound', label: 'Inbound — recibe llamadas' },
                      { value: 'outbound', label: 'Outbound — hace llamadas' },
                      { value: 'both', label: 'Ambos' },
                    ]}
                  />

                  {/* Conversation mode */}
                  <div>
                    <label className="block text-xs text-text-muted mb-2">Modo de conversacion</label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setForm(f => ({ ...f, conversation_mode: 'prompt' }))}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors cursor-pointer ${
                          form.conversation_mode === 'prompt'
                            ? 'border-accent bg-accent/10 text-accent'
                            : 'border-border text-text-muted hover:border-text-muted'
                        }`}
                      >
                        Prompt libre
                      </button>
                      <button
                        type="button"
                        onClick={() => setForm(f => ({ ...f, conversation_mode: 'flow' }))}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors cursor-pointer ${
                          form.conversation_mode === 'flow'
                            ? 'border-accent bg-accent/10 text-accent'
                            : 'border-border text-text-muted hover:border-text-muted'
                        }`}
                      >
                        Flujo visual
                      </button>
                    </div>
                    {form.conversation_mode === 'flow' && (
                      <button
                        type="button"
                        onClick={() => navigate(`/agents/${selectedAgent.id}/flow`)}
                        className="mt-3 w-full px-4 py-2.5 rounded-lg border border-accent/30 bg-accent/5
                                   text-accent text-sm font-medium hover:bg-accent/10 transition-colors
                                   flex items-center justify-center gap-2 cursor-pointer"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                        </svg>
                        Editar flujo de conversacion
                      </button>
                    )}
                    <p className="text-[10px] text-text-muted mt-2">
                      {form.conversation_mode === 'prompt'
                        ? 'El agente usa el system prompt para improvisar la conversacion.'
                        : 'El agente sigue un flujo predefinido con pasos y condiciones.'}
                    </p>
                  </div>

                  {/* Templates */}
                  {templates.length > 0 && (
                    <div>
                      <label className="block text-xs text-text-muted mb-1">
                        <FileText size={12} className="inline mr-1" />
                        Plantilla de industria
                      </label>
                      <select
                        value=""
                        onChange={async (e) => {
                          if (!e.target.value) return
                          try {
                            const tpl = await api.get(
                              `/clients/templates/${e.target.value}?agent_name=${encodeURIComponent(form.name)}&business_name=${encodeURIComponent(client.name)}`
                            )
                            setForm(f => ({ ...f, system_prompt: tpl.content }))
                            toast.success('Plantilla aplicada. Puedes editarla.')
                          } catch (err) {
                            toast.error(err.message)
                          }
                        }}
                        className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent cursor-pointer"
                      >
                        <option value="">Seleccionar plantilla...</option>
                        {templates.map(t => (
                          <option key={t.key} value={t.key}>{t.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </Card>

                {/* Right column: Messages */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary">Mensajes</h2>

                  <Textarea
                    label="Saludo"
                    value={form.greeting}
                    onChange={e => setForm(f => ({ ...f, greeting: e.target.value }))}
                    rows={3}
                  />

                  <div className="flex items-center justify-between">
                    <label className="block text-xs text-text-muted">System prompt</label>
                    <div className="flex items-center gap-2">
                      <PromptAssistant
                        type="agent"
                        currentPrompt={form.system_prompt}
                        onApply={prompt => setForm(f => ({ ...f, system_prompt: prompt }))}
                        agentName={form.name}
                        businessName={client.name}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPreview(true)}
                        className="text-xs text-text-muted hover:text-text-primary flex items-center gap-1 cursor-pointer"
                      >
                        <Eye size={12} /> Vista previa
                      </button>
                    </div>
                  </div>
                  <Textarea
                    value={form.system_prompt}
                    onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))}
                    rows={8}
                  />

                  <Textarea
                    label="Ejemplos de conversacion (few-shot)"
                    value={form.examples}
                    onChange={e => setForm(f => ({ ...f, examples: e.target.value }))}
                    rows={4}
                    placeholder={"Paciente: Cuanto cuesta una limpieza?\nAgente: Mire, la limpieza dental tiene un costo de $800..."}
                  />

                  <Textarea
                    label="Mensaje fuera de horario"
                    value={form.after_hours_message}
                    onChange={e => setForm(f => ({ ...f, after_hours_message: e.target.value }))}
                    rows={2}
                  />
                </Card>
              </div>
            )}

            {/* ── Voz Tab ── */}
            {activeTab === 'voice' && (
              <div className="space-y-6">
                <Card className="space-y-5">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Zap size={16} className="text-accent" />
                    Pipeline de Voz
                  </h2>

                  <p className="text-xs text-text-muted">
                    Configura los proveedores de voz de este agente. Los proveedores incluidos usan las
                    API keys de la plataforma. Para otros proveedores, necesitas tu propia API key.
                  </p>

                  {/* Mode toggle: Pipeline vs Realtime */}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setForm(f => ({ ...f, agent_mode: 'pipeline' }))}
                      className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-all cursor-pointer ${
                        isPipeline
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-border bg-bg-primary text-text-muted hover:bg-bg-hover'
                      }`}
                    >
                      <div className="flex items-center justify-center gap-2">
                        <Mic size={16} />
                        <span>Pipeline</span>
                      </div>
                      <p className="text-[11px] mt-1 font-normal opacity-70">STT + LLM + TTS separados</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm(f => ({ ...f, agent_mode: 'realtime' }))}
                      className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-all cursor-pointer ${
                        !isPipeline
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-border bg-bg-primary text-text-muted hover:bg-bg-hover'
                      }`}
                    >
                      <div className="flex items-center justify-center gap-2">
                        <Zap size={16} />
                        <span>OpenAI Realtime</span>
                      </div>
                      <p className="text-[11px] mt-1 font-normal opacity-70">Modelo multimodal end-to-end</p>
                    </button>
                  </div>

                  {isPipeline ? (
                    <div className="space-y-5">
                      {/* STT */}
                      <div className="p-4 rounded-lg border border-border bg-bg-primary/50">
                        <div className="flex items-center gap-2 mb-3">
                          <Mic size={16} className="text-blue-400" />
                          <span className="text-sm font-medium">Speech-to-Text (STT)</span>
                        </div>
                        <PipelineSelect
                          value={form.stt_provider}
                          onChange={v => setForm(f => ({ ...f, stt_provider: v }))}
                          options={STT_OPTIONS.map(o => ({
                            value: o.value,
                            label: o.label + (o.included ? ' (incluido)' : ' (tu API key)'),
                          }))}
                        />
                        {needsKey('stt') && (
                          <div className="mt-3">
                            <ApiKeyField
                              label="API Key"
                              hasKey={serverKeys.has_stt_api_key}
                              value={form.stt_api_key}
                              onChange={v => setForm(f => ({ ...f, stt_api_key: v }))}
                              onClear={() => clearApiKey('stt_api_key', 'has_stt_api_key')}
                            />
                          </div>
                        )}
                      </div>

                      {/* LLM */}
                      <div className="p-4 rounded-lg border border-border bg-bg-primary/50">
                        <div className="flex items-center gap-2 mb-3">
                          <Brain size={16} className="text-purple-400" />
                          <span className="text-sm font-medium">Modelo de Lenguaje (LLM)</span>
                        </div>
                        <PipelineSelect
                          value={form.llm_provider}
                          onChange={v => setForm(f => ({ ...f, llm_provider: v }))}
                          options={LLM_OPTIONS.map(o => ({
                            value: o.value,
                            label: o.label + (o.included ? ' (incluido)' : ' (tu API key)'),
                          }))}
                        />
                        {needsKey('llm') && (
                          <div className="mt-3">
                            <ApiKeyField
                              label="API Key"
                              hasKey={serverKeys.has_llm_api_key}
                              value={form.llm_api_key}
                              onChange={v => setForm(f => ({ ...f, llm_api_key: v }))}
                              onClear={() => clearApiKey('llm_api_key', 'has_llm_api_key')}
                            />
                          </div>
                        )}
                      </div>

                      {/* TTS */}
                      <div className="p-4 rounded-lg border border-border bg-bg-primary/50">
                        <div className="flex items-center gap-2 mb-3">
                          <Volume2 size={16} className="text-green-400" />
                          <span className="text-sm font-medium">Text-to-Speech (TTS)</span>
                        </div>
                        <PipelineSelect
                          value={form.tts_provider}
                          onChange={v => setForm(f => ({ ...f, tts_provider: v }))}
                          options={TTS_OPTIONS.map(o => ({
                            value: o.value,
                            label: o.label + (o.included ? ' (incluido)' : ' (tu API key)'),
                          }))}
                        />
                        {needsKey('tts') && (
                          <div className="mt-3">
                            <ApiKeyField
                              label="API Key"
                              hasKey={serverKeys.has_tts_api_key}
                              value={form.tts_api_key}
                              onChange={v => setForm(f => ({ ...f, tts_api_key: v }))}
                              onClear={() => clearApiKey('tts_api_key', 'has_tts_api_key')}
                            />
                          </div>
                        )}
                      </div>

                      {/* Cost estimator */}
                      <CostEstimator
                        sttProvider={form.stt_provider}
                        llmProvider={form.llm_provider}
                        ttsProvider={form.tts_provider}
                      />

                      {/* Voice selector */}
                      <div className="p-4 rounded-lg border border-border bg-bg-primary/50">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <Volume2 size={16} className="text-accent" />
                            <span className="text-sm font-medium">Voz del agente</span>
                          </div>
                          {form.tts_provider !== 'cartesia' && (
                            <button
                              type="button"
                              onClick={handleRefreshVoices}
                              className="text-xs text-accent hover:text-accent/80 flex items-center gap-1 cursor-pointer"
                              title="Recargar voces"
                            >
                              <RefreshCw size={12} /> Recargar
                            </button>
                          )}
                        </div>

                        {loadingVoices ? (
                          <div className="flex items-center gap-2 py-2 text-xs text-text-muted">
                            <Spinner size={14} /> Cargando voces de {PROVIDER_LABELS[form.tts_provider] || form.tts_provider}...
                          </div>
                        ) : filteredVoices.length === 0 ? (
                          <p className="text-xs text-text-muted py-2">
                            No se encontraron voces. Verifica tu API key.
                          </p>
                        ) : (
                          <>
                            <select
                              value={form.voice_id || ''}
                              onChange={e => setForm(f => ({ ...f, voice_id: e.target.value }))}
                              className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent cursor-pointer"
                            >
                              <option value="">Seleccionar voz...</option>
                              {Object.entries(groupedVoices).map(([group, groupVoices]) => (
                                <optgroup key={group} label={group}>
                                  {groupVoices.map(v => (
                                    <option key={v.id} value={v.id}>
                                      {v.name} — {v.description}
                                    </option>
                                  ))}
                                </optgroup>
                              ))}
                            </select>
                            {currentVoice && (
                              <p className="text-xs text-text-muted mt-1">
                                {currentVoice.name} ({currentVoice.gender === 'female' ? '\u2640' : currentVoice.gender === 'male' ? '\u2642' : '\u26A1'}) — {currentVoice.description}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ) : (
                    /* Realtime config */
                    <div className="space-y-4 p-4 rounded-lg border border-border bg-bg-primary/50">
                      <div className="flex items-center gap-2 mb-1">
                        <Key size={16} className="text-amber-400" />
                        <span className="text-sm font-medium">Configuracion OpenAI Realtime</span>
                      </div>
                      <ApiKeyField
                        label="OpenAI API Key (requerido)"
                        hasKey={serverKeys.has_realtime_api_key}
                        value={form.realtime_api_key}
                        onChange={v => setForm(f => ({ ...f, realtime_api_key: v }))}
                        onClear={() => clearApiKey('realtime_api_key', 'has_realtime_api_key')}
                      />
                      <PipelineSelect
                        label="Modelo"
                        value={form.realtime_model}
                        onChange={v => setForm(f => ({ ...f, realtime_model: v }))}
                        options={REALTIME_MODELS}
                      />
                      <PipelineSelect
                        label="Voz"
                        value={form.realtime_voice}
                        onChange={v => setForm(f => ({ ...f, realtime_voice: v }))}
                        options={REALTIME_VOICES.map(v => ({
                          value: v.value,
                          label: `${v.label} — ${v.desc}`,
                        }))}
                      />
                    </div>
                  )}
                </Card>
              </div>
            )}

            {/* ── Llamadas Tab ── */}
            {activeTab === 'calls' && (
              <Card className="space-y-4">
                <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                  <Phone size={16} className="text-accent" />
                  Configuracion de llamadas
                </h2>

                <Input
                  label="Duracion maxima (segundos)"
                  type="number"
                  value={form.max_call_duration_seconds}
                  onChange={e => setForm(f => ({ ...f, max_call_duration_seconds: parseInt(e.target.value) || 300 }))}
                />

                <Input
                  label="Numero de transferencia"
                  value={form.transfer_number}
                  onChange={e => setForm(f => ({ ...f, transfer_number: e.target.value }))}
                  placeholder="+52..."
                />

                {/* Phone number (readonly) */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-text-muted">Numero de telefono</label>
                  <p className="text-sm font-mono bg-bg-secondary border border-border rounded-lg px-3 py-2">
                    {selectedAgent.phone_number || <span className="text-text-muted">Sin asignar</span>}
                  </p>
                </div>

                {/* Status */}
                <Select
                  label="Estado"
                  value={form.is_active ? 'true' : 'false'}
                  onChange={e => setForm(f => ({ ...f, is_active: e.target.value === 'true' }))}
                  options={[
                    { value: 'true', label: 'Activo' },
                    { value: 'false', label: 'Inactivo' },
                  ]}
                />

                {/* Slug (readonly) */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-text-muted">Slug</label>
                  <p className="text-sm font-mono bg-bg-secondary border border-border rounded-lg px-3 py-2">
                    {selectedAgent.slug || <span className="text-text-muted">—</span>}
                  </p>
                </div>
              </Card>
            )}

            {/* ── WhatsApp Tab ── */}
            {activeTab === 'whatsapp' && clientId && selectedAgent && (
              <WhatsAppConfig clientId={clientId} agentId={selectedAgent.id} />
            )}

            {/* ── Avanzado Tab ── */}
            {activeTab === 'advanced' && (
              <div className="space-y-6">
                {/* Orchestration role */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Zap size={16} className="text-purple-400" />
                    Rol para Orquestacion
                    {client.orchestration_mode === 'intelligent' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-medium">Modo Inteligente activo</span>
                    )}
                  </h2>
                  <p className="text-xs text-text-muted">
                    Describe que hace este agente para que el coordinador IA sepa cuando derivarle llamadas.
                    {client.orchestration_mode !== 'intelligent' && (
                      <span className="text-yellow-400/80"> El Modo Inteligente no esta activo aun — puedes configurar el rol ahora y activarlo despues.</span>
                    )}
                  </p>
                  <Textarea
                    label="Descripcion del rol"
                    value={form.role_description}
                    onChange={e => setForm(f => ({ ...f, role_description: e.target.value }))}
                    rows={3}
                    placeholder="Ej: Agente de ventas especializado en cotizaciones y cierre de ventas. Responde preguntas sobre precios, paquetes y promociones."
                  />
                  <Input
                    label="Prioridad (mayor = mas probable como default)"
                    type="number"
                    value={form.orchestrator_priority}
                    onChange={e => setForm(f => ({ ...f, orchestrator_priority: parseInt(e.target.value) || 0 }))}
                  />
                  <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.orchestrator_enabled}
                      onChange={e => setForm(f => ({ ...f, orchestrator_enabled: e.target.checked }))}
                      className="accent-purple-400"
                    />
                    Habilitado para orquestacion
                  </label>
                </Card>

                {/* Delete agent */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-red-400">Zona de peligro</h2>
                  <p className="text-xs text-text-muted">
                    Eliminar este agente es una accion permanente. Se perdera toda su configuracion, historial de llamadas y datos asociados.
                  </p>
                  <Button variant="danger" onClick={handleDelete}>
                    <Trash2 size={16} className="mr-2 inline" /> Eliminar agente
                  </Button>
                </Card>
              </div>
            )}
          </div>

          {/* ── Bottom bar: Save + ChatTester (always visible when agent selected) ── */}
          <div className="flex items-center gap-3 pt-2 border-t border-border">
            <Button onClick={handleSave} disabled={saving}>
              <Save size={16} className="mr-2 inline" />
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </Button>
            <ChatTesterButton
              agentId={selectedAgent.id}
              agentName={form.name}
              agentType={form.agent_type}
            />
          </div>
        </>
      )}

      {/* ── No agent selected ── */}
      {!selectedAgent && agents.length === 0 && (
        <Card className="text-center py-12 space-y-4">
          <Bot size={48} className="mx-auto text-text-muted" />
          <p className="text-text-secondary">No tienes agentes aun.</p>
          <Button onClick={() => setShowCreateAgent(true)}>
            <Plus size={16} className="mr-2 inline" /> Crear tu primer agente
          </Button>
        </Card>
      )}

      {/* ── Preview Modal ── */}
      {showPreview && selectedAgent && (
        <Modal open={true} title="Vista previa del prompt" onClose={() => setShowPreview(false)}>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            <div>
              <h3 className="text-xs font-semibold text-text-muted mb-1">System Prompt</h3>
              <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{form.system_prompt}</pre>
            </div>
            {form.examples && (
              <div>
                <h3 className="text-xs font-semibold text-text-muted mb-1">Ejemplos de conversacion</h3>
                <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{form.examples}</pre>
              </div>
            )}
            <p className="text-[10px] text-text-muted">
              * Las reglas de voz y herramientas se agregan automaticamente al prompt en tiempo de ejecucion.
            </p>
          </div>
        </Modal>
      )}

      {/* ── Create Agent Modal ── */}
      {showCreateAgent && (
        <Modal open={true} title="Nuevo agente" onClose={() => setShowCreateAgent(false)}>
          <form onSubmit={handleCreateAgent} className="space-y-4">
            <Input
              label="Nombre del agente"
              value={newAgentForm.name}
              onChange={e => setNewAgentForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Ej: Sofia, Carlos, Recepcionista..."
              required
            />
            <Select
              label="Tipo"
              value={newAgentForm.agent_type}
              onChange={e => setNewAgentForm(f => ({ ...f, agent_type: e.target.value }))}
              options={[
                { value: 'inbound', label: 'Inbound — recibe llamadas' },
                { value: 'outbound', label: 'Outbound — hace llamadas' },
                { value: 'both', label: 'Ambos' },
              ]}
            />
            <Textarea
              label="Rol del agente (para el coordinador IA)"
              value={newAgentForm.role_description}
              onChange={e => setNewAgentForm(f => ({ ...f, role_description: e.target.value }))}
              rows={2}
              placeholder="Ej: Agente de ventas que maneja cotizaciones. Soporte tecnico que resuelve problemas."
            />
            <p className="text-xs text-text-muted">
              El rol describe que hace este agente para que el coordinador sepa cuando derivar llamadas.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" type="button" onClick={() => setShowCreateAgent(false)}>Cancelar</Button>
              <Button type="submit" disabled={creatingAgent}>
                {creatingAgent ? 'Creando...' : 'Crear agente'}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
