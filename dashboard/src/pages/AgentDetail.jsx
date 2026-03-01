import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Save, Trash2, Volume2, Mic, Brain, Zap, Key,
  ChevronDown, ChevronUp, Check, RefreshCw,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader, Spinner } from '../components/ui/Spinner'
import { PromptAssistant } from '../components/PromptAssistant'
import { ChatTesterButton } from '../components/ChatTester'

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

export function AgentDetail() {
  const { agentId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [voices, setVoices] = useState([])
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [pipelineOpen, setPipelineOpen] = useState(false)

  const [clientData, setClientData] = useState(null)

  // Form state para campos del agente
  const [form, setForm] = useState({
    name: '',
    slug: '',
    agent_type: 'inbound',
    phone_number: '',
    max_call_duration_seconds: 300,
    transfer_number: '',
    is_active: true,
    greeting: '',
    system_prompt: '',
    examples: '',
    after_hours_message: '',
    // Pipeline
    agent_mode: 'pipeline',
    stt_provider: 'deepgram',
    llm_provider: 'google',
    tts_provider: 'cartesia',
    stt_api_key: '',
    llm_api_key: '',
    tts_api_key: '',
    realtime_api_key: '',
    realtime_voice: 'alloy',
    realtime_model: 'gpt-4o-realtime-preview',
    voice_id: '',
    // Orchestration
    role_description: '',
    orchestrator_enabled: true,
    orchestrator_priority: 0,
  })

  // Track si las API keys existen en el servidor
  const [serverKeys, setServerKeys] = useState({
    has_stt_api_key: false,
    has_llm_api_key: false,
    has_tts_api_key: false,
    has_realtime_api_key: false,
  })

  // Determinar clientId: del agente cargado o del usuario
  const clientId = agent?.client_id || user?.client_id

  // Cargar agente al montar
  useEffect(() => {
    loadAgent()
  }, [agentId])

  async function loadAgent() {
    setLoading(true)
    try {
      // Primero intentar cargar con client_id del usuario, si no es admin usar directamente
      const cid = user?.client_id
      let agentData
      if (user?.role === 'admin') {
        // Admin: necesitamos buscar el agente — intentar cargarlo via lista de clientes
        // Usamos un endpoint que acepta agentId directamente
        // Intentar con cada cliente hasta encontrar o usar un endpoint generico
        // Asumimos que hay un endpoint: GET /clients/{clientId}/agents/{agentId}
        // Pero no sabemos el clientId aun. Podemos usar un endpoint admin alternativo.
        // Intentar buscar todos los clientes y encontrar el agente
        const clients = await api.get('/clients')
        for (const c of clients) {
          try {
            agentData = await api.get(`/clients/${c.id}/agents/${agentId}`)
            break
          } catch { /* continuar */ }
        }
        if (!agentData) throw new Error('Agente no encontrado')
      } else {
        agentData = await api.get(`/clients/${cid}/agents/${agentId}`)
      }

      setAgent(agentData)

      // Extraer config del agente
      const voiceConfig = agentData.voice_config || {}
      const llmConfig = agentData.llm_config || {}
      const sttConfig = agentData.stt_config || {}

      setForm({
        name: agentData.name || '',
        slug: agentData.slug || '',
        agent_type: agentData.agent_type || 'inbound',
        phone_number: agentData.phone_number || '',
        max_call_duration_seconds: agentData.max_call_duration_seconds || 300,
        transfer_number: agentData.transfer_number || '',
        is_active: agentData.is_active !== false,
        greeting: agentData.greeting || '',
        system_prompt: agentData.system_prompt || '',
        examples: agentData.examples || '',
        after_hours_message: agentData.after_hours_message || '',
        agent_mode: agentData.agent_mode || 'pipeline',
        stt_provider: sttConfig.provider || 'deepgram',
        llm_provider: llmConfig.provider || 'google',
        tts_provider: voiceConfig.provider || 'cartesia',
        stt_api_key: '',
        llm_api_key: '',
        tts_api_key: '',
        realtime_api_key: '',
        realtime_voice: voiceConfig.realtime_voice || 'alloy',
        realtime_model: voiceConfig.realtime_model || 'gpt-4o-realtime-preview',
        voice_id: voiceConfig.voice_id || '',
        role_description: agentData.role_description || '',
        orchestrator_enabled: agentData.orchestrator_enabled !== false,
        orchestrator_priority: agentData.orchestrator_priority || 0,
      })

      // Cargar datos del cliente para saber si orchestration_mode es intelligent
      try {
        const cData = await api.get(`/clients/${agentData.client_id}`)
        setClientData(cData)
      } catch { /* ignore */ }

      setServerKeys({
        has_stt_api_key: sttConfig.has_api_key || false,
        has_llm_api_key: llmConfig.has_api_key || false,
        has_tts_api_key: voiceConfig.has_api_key || false,
        has_realtime_api_key: voiceConfig.has_realtime_api_key || false,
      })

      // Cargar voces
      await loadVoicesForAgent(agentData)
    } catch (err) {
      console.error('Error cargando agente:', err)
      toast.error(err.message || 'Error cargando agente')
      navigate(user?.role === 'admin' ? '/admin/clients' : '/settings')
    } finally {
      setLoading(false)
    }
  }

  async function loadVoicesForAgent(agentData) {
    const voiceConfig = agentData?.voice_config || {}
    const provider = voiceConfig.provider || 'cartesia'
    const mode = agentData?.agent_mode || 'pipeline'
    const cid = agentData?.client_id || user?.client_id

    if (mode === 'realtime') {
      setVoices([])
      return
    }

    setLoadingVoices(true)
    try {
      if (provider === 'elevenlabs' || provider === 'openai') {
        const v = await api.get(`/voices/provider/${cid}?agent_id=${agentId}`)
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

  async function handleRefreshVoices() {
    if (!agent) return
    await loadVoicesForAgent(agent)
    toast.success('Voces actualizadas')
  }

  async function handleSave() {
    if (!agent || !clientId) return
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
      }

      // Solo enviar API keys si se escribieron nuevas
      if (form.stt_api_key) payload.stt_api_key = form.stt_api_key
      if (form.llm_api_key) payload.llm_api_key = form.llm_api_key
      if (form.tts_api_key) payload.tts_api_key = form.tts_api_key
      if (form.realtime_api_key) payload.realtime_api_key = form.realtime_api_key

      const updated = await api.patch(`/clients/${clientId}/agents/${agentId}`, payload)
      setAgent(updated)

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
      setForm(f => ({
        ...f,
        stt_api_key: '', llm_api_key: '', tts_api_key: '', realtime_api_key: '',
      }))

      toast.success('Agente guardado')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!agent || !clientId) return
    const ok = await confirm({
      title: 'Eliminar agente',
      message: `¿Eliminar "${agent.name}"? Esta accion no se puede deshacer.`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${clientId}/agents/${agentId}`)
      toast.success('Agente eliminado')
      navigate(user?.role === 'admin' ? `/admin/clients/${clientId}` : '/settings')
    } catch (err) {
      toast.error(err.message)
    }
  }

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

  // Voces filtradas y agrupadas
  const filteredVoices = useMemo(() => {
    if (!voices?.length) return []
    if (form.tts_provider !== 'cartesia') return voices
    return voices
  }, [voices, form.tts_provider])

  const groupedVoices = useMemo(() => {
    const groups = {}
    for (const v of filteredVoices) {
      let key
      if (form.tts_provider === 'cartesia') {
        const lang = v.language === 'es' ? 'Espanol' : 'English'
        const gender = v.gender === 'female' ? 'Mujeres' : 'Hombres'
        key = `${lang} — ${gender}`
      } else {
        const g = v.gender || 'unknown'
        key = g === 'female' ? 'Mujeres' : g === 'male' ? 'Hombres' : 'Voces'
      }
      if (!groups[key]) groups[key] = []
      groups[key].push(v)
    }
    return groups
  }, [filteredVoices, form.tts_provider])

  const currentVoice = voices?.find(v => v.id === form.voice_id)

  if (loading) return <PageLoader />
  if (!agent) return null

  const isPipeline = form.agent_mode === 'pipeline'
  const backPath = user?.role === 'admin' ? `/admin/clients/${clientId}` : '/settings'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate(backPath)}>
          <ArrowLeft size={16} />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{agent.name}</h1>
          <span className="text-text-muted font-mono text-sm">{agent.slug}</span>
        </div>
      </div>

      {/* 2-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Configuracion del agente */}
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Configuracion del agente</h2>

          <Input
            label="Nombre"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          />

          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-text-secondary">Slug</label>
            <p className="text-sm text-text-muted font-mono bg-bg-secondary border border-border rounded-lg px-3 py-2">
              {form.slug}
            </p>
          </div>

          <Select
            label="Tipo"
            value={form.agent_type}
            onChange={e => setForm(f => ({ ...f, agent_type: e.target.value }))}
            options={[
              { value: 'inbound', label: 'Inbound' },
              { value: 'outbound', label: 'Outbound' },
              { value: 'both', label: 'Both' },
            ]}
          />

          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-text-secondary">Numero de telefono</label>
            <p className="text-sm font-mono bg-bg-secondary border border-border rounded-lg px-3 py-2">
              {form.phone_number || <span className="text-text-muted">Sin asignar</span>}
            </p>
          </div>

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

          <Select
            label="Estado"
            value={form.is_active ? 'true' : 'false'}
            onChange={e => setForm(f => ({ ...f, is_active: e.target.value === 'true' }))}
            options={[
              { value: 'true', label: 'Activo' },
              { value: 'false', label: 'Inactivo' },
            ]}
          />
        </Card>

        {/* Right: Mensajes */}
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
            <PromptAssistant
              type="agent"
              currentPrompt={form.system_prompt}
              onApply={prompt => setForm(f => ({ ...f, system_prompt: prompt }))}
              agentName={form.name}
              businessName={agent.client_name || ''}
            />
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
            placeholder={"Paciente: ¿Cuanto cuesta una limpieza?\nAgente: Mire, la limpieza dental tiene un costo de $800..."}
          />

          <Textarea
            label="Mensaje fuera de horario"
            value={form.after_hours_message}
            onChange={e => setForm(f => ({ ...f, after_hours_message: e.target.value }))}
            rows={2}
          />
        </Card>
      </div>

      {/* Voice Pipeline (collapsible) */}
      <Card className="space-y-0">
        <button
          type="button"
          onClick={() => setPipelineOpen(p => !p)}
          className="w-full flex items-center justify-between cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Zap size={20} className="text-accent" />
            <h2 className="text-lg font-semibold">Pipeline de Voz</h2>
          </div>
          {pipelineOpen
            ? <ChevronUp size={20} className="text-text-muted" />
            : <ChevronDown size={20} className="text-text-muted" />
          }
        </button>

        {pipelineOpen && (
          <div className="mt-5 space-y-5">
            <p className="text-xs text-text-muted">
              Configura los proveedores de voz de este agente. Los proveedores incluidos usan las
              API keys de la plataforma. Para otros proveedores, necesitas tu propia API key.
            </p>

            {/* Mode toggle */}
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
                      <Spinner size={14} /> Cargando voces...
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
                        className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
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
          </div>
        )}
      </Card>

      {/* Orchestration card — solo si el cliente tiene modo inteligente */}
      {clientData?.orchestration_mode === 'intelligent' && (
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
            <Zap size={16} className="text-purple-400" />
            Orquestacion (Modo Inteligente)
          </h2>
          <p className="text-xs text-text-muted">
            Este cliente tiene Modo Inteligente activo. Configura como el coordinador percibe este agente.
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
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={saving}>
          <Save size={16} className="mr-2 inline" />
          {saving ? 'Guardando...' : 'Guardar'}
        </Button>
        <ChatTesterButton
          agentId={agentId}
          agentName={agent.name}
          agentType={agent.agent_type}
        />
        <Button variant="danger" onClick={handleDelete}>
          <Trash2 size={16} className="mr-2 inline" /> Eliminar
        </Button>
      </div>
    </div>
  )
}
