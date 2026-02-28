import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PageLoader } from '../components/ui/Spinner'
import {
  Calendar, MessageCircle, Wrench, Save, TestTube, Check,
  Mic, Brain, Volume2, Zap, Key, ChevronDown,
} from 'lucide-react'

const allTools = [
  { key: 'search_knowledge', label: 'Busqueda de conocimientos', desc: 'Consultar base de documentos del negocio' },
  { key: 'schedule_appointment', label: 'Agendar citas', desc: 'El agente puede crear citas durante la llamada' },
  { key: 'send_whatsapp', label: 'Enviar WhatsApp', desc: 'Enviar mensajes de confirmacion por WhatsApp' },
  { key: 'save_contact', label: 'Capturar contactos', desc: 'Guardar datos de contacto del interlocutor' },
]

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
  'alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar',
]

const REALTIME_MODELS = [
  'gpt-4o-realtime-preview',
  'gpt-4o-mini-realtime-preview',
]

function Select({ label, value, onChange, options, icon: Icon }) {
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

export function Integrations() {
  const { user } = useAuth()
  const toast = useToast()
  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingWa, setTestingWa] = useState(false)
  const [testingCal, setTestingCal] = useState(false)

  const [form, setForm] = useState({
    google_calendar_id: '',
    whatsapp_instance_id: '',
    whatsapp_api_url: '',
    whatsapp_api_key: '',
    enabled_tools: ['search_knowledge'],
    // BYOK
    voice_mode: 'pipeline',
    stt_provider: 'deepgram',
    llm_provider: 'google',
    tts_provider: 'cartesia',
    stt_api_key: '',
    llm_api_key: '',
    tts_api_key: '',
    realtime_api_key: '',
    realtime_voice: 'alloy',
    realtime_model: 'gpt-4o-realtime-preview',
  })

  // Track cuales keys existen en el servidor (para mostrar "Configurada")
  const [serverKeys, setServerKeys] = useState({
    has_stt_api_key: false,
    has_llm_api_key: false,
    has_tts_api_key: false,
    has_realtime_api_key: false,
  })

  const clientId = user?.client_id

  useEffect(() => {
    if (!clientId) return
    api.get(`/clients/${clientId}`)
      .then(c => {
        setClient(c)
        setServerKeys({
          has_stt_api_key: c.has_stt_api_key || false,
          has_llm_api_key: c.has_llm_api_key || false,
          has_tts_api_key: c.has_tts_api_key || false,
          has_realtime_api_key: c.has_realtime_api_key || false,
        })
        setForm({
          google_calendar_id: c.google_calendar_id || '',
          whatsapp_instance_id: c.whatsapp_instance_id || '',
          whatsapp_api_url: c.whatsapp_api_url || '',
          whatsapp_api_key: '',  // Nunca recibimos la key real del server
          enabled_tools: c.enabled_tools || ['search_knowledge'],
          voice_mode: c.voice_mode || 'pipeline',
          stt_provider: c.stt_provider || 'deepgram',
          llm_provider: c.llm_provider || 'google',
          tts_provider: c.tts_provider || 'cartesia',
          stt_api_key: '',
          llm_api_key: '',
          tts_api_key: '',
          realtime_api_key: '',
          realtime_voice: c.realtime_voice || 'alloy',
          realtime_model: c.realtime_model || 'gpt-4o-realtime-preview',
        })
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  async function handleSave() {
    setSaving(true)
    try {
      // Solo enviar keys si el usuario escribio algo nuevo
      const payload = { ...form }
      if (!payload.stt_api_key) delete payload.stt_api_key
      if (!payload.llm_api_key) delete payload.llm_api_key
      if (!payload.tts_api_key) delete payload.tts_api_key
      if (!payload.realtime_api_key) delete payload.realtime_api_key
      if (!payload.whatsapp_api_key) delete payload.whatsapp_api_key

      const updated = await api.patch(`/clients/${clientId}`, payload)
      setClient(updated)
      setServerKeys({
        has_stt_api_key: updated.has_stt_api_key || false,
        has_llm_api_key: updated.has_llm_api_key || false,
        has_tts_api_key: updated.has_tts_api_key || false,
        has_realtime_api_key: updated.has_realtime_api_key || false,
      })
      // Limpiar keys del form ya que se guardaron
      setForm(f => ({
        ...f,
        stt_api_key: '', llm_api_key: '', tts_api_key: '',
        realtime_api_key: '', whatsapp_api_key: '',
      }))
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTestWhatsApp() {
    setTestingWa(true)
    try {
      const res = await api.post(`/clients/${clientId}/test-whatsapp`)
      toast.success(res.message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTestingWa(false)
    }
  }

  async function handleTestCalendar() {
    setTestingCal(true)
    try {
      const res = await api.post(`/clients/${clientId}/test-calendar`)
      toast.success(res.message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTestingCal(false)
    }
  }

  function toggleTool(key) {
    setForm(f => ({
      ...f,
      enabled_tools: f.enabled_tools.includes(key)
        ? f.enabled_tools.filter(t => t !== key)
        : [...f.enabled_tools, key],
    }))
  }

  function clearApiKey(field, serverField) {
    // Enviar string vacio para borrar la key en el server
    setForm(f => ({ ...f, [field]: '' }))
    setServerKeys(s => ({ ...s, [serverField]: false }))
    // Marcar para enviar null en el save
    setForm(f => ({ ...f, [`_clear_${field}`]: true }))
  }

  // Determina si un provider necesita BYOK key
  function needsKey(type) {
    const opt = {
      stt: STT_OPTIONS, llm: LLM_OPTIONS, tts: TTS_OPTIONS,
    }[type]?.find(o => o.value === form[`${type}_provider`])
    return opt && !opt.included
  }

  if (loading) return <PageLoader />
  if (!client) return <p className="text-text-muted text-center py-12">No tienes un cliente asignado</p>

  const isPipeline = form.voice_mode === 'pipeline'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Integraciones</h1>
        <Button onClick={handleSave} disabled={saving}>
          <Save size={16} className="mr-1" /> {saving ? 'Guardando...' : 'Guardar todo'}
        </Button>
      </div>

      {/* Voice Pipeline */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Zap size={20} className="text-accent" />
          <h2 className="text-lg font-semibold">Pipeline de Voz</h2>
        </div>
        <p className="text-xs text-text-muted mb-5">
          Configura los proveedores de voz de tu agente. Los proveedores incluidos usan las
          API keys de la plataforma. Para otros proveedores, necesitas tu propia API key.
        </p>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setForm(f => ({ ...f, voice_mode: 'pipeline' }))}
            className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
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
            onClick={() => setForm(f => ({ ...f, voice_mode: 'realtime' }))}
            className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
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
              <Select
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
              <Select
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
              <Select
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
            <Select
              label="Modelo"
              value={form.realtime_model}
              onChange={v => setForm(f => ({ ...f, realtime_model: v }))}
              options={REALTIME_MODELS.map(m => ({ value: m, label: m }))}
            />
            <Select
              label="Voz"
              value={form.realtime_voice}
              onChange={v => setForm(f => ({ ...f, realtime_voice: v }))}
              options={REALTIME_VOICES.map(v => ({ value: v, label: v.charAt(0).toUpperCase() + v.slice(1) }))}
            />
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Google Calendar */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Calendar size={20} className="text-accent" />
            <h2 className="text-lg font-semibold">Google Calendar</h2>
          </div>
          <p className="text-xs text-text-muted mb-4">
            Conecta tu calendario de Google para que las citas agendadas por el agente
            se sincronicen automaticamente.
          </p>
          <div className="space-y-3">
            <Input
              label="Calendar ID"
              value={form.google_calendar_id}
              onChange={e => setForm(f => ({ ...f, google_calendar_id: e.target.value }))}
              placeholder="usuario@gmail.com o ID del calendario"
            />
            <p className="text-[11px] text-text-muted">
              La Service Account Key se configura desde el panel de admin.
            </p>
            <Button
              variant="secondary"
              onClick={handleTestCalendar}
              disabled={testingCal || !form.google_calendar_id}
              className="text-xs"
            >
              <TestTube size={14} className="mr-1" />
              {testingCal ? 'Probando...' : 'Probar conexion'}
            </Button>
          </div>
        </Card>

        {/* WhatsApp */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <MessageCircle size={20} className="text-success" />
            <h2 className="text-lg font-semibold">WhatsApp</h2>
          </div>
          <p className="text-xs text-text-muted mb-4">
            Conecta Evolution API para enviar mensajes de WhatsApp
            (confirmaciones de citas, informacion, etc).
          </p>
          <div className="space-y-3">
            <Input
              label="URL de API"
              value={form.whatsapp_api_url}
              onChange={e => setForm(f => ({ ...f, whatsapp_api_url: e.target.value }))}
              placeholder="https://evo.example.com"
            />
            <Input
              label="Instance ID"
              value={form.whatsapp_instance_id}
              onChange={e => setForm(f => ({ ...f, whatsapp_instance_id: e.target.value }))}
              placeholder="mi-instancia"
            />
            <Input
              label="API Key"
              type="password"
              value={form.whatsapp_api_key}
              onChange={e => setForm(f => ({ ...f, whatsapp_api_key: e.target.value }))}
              placeholder="evo-api-key..."
            />
            <Button
              variant="secondary"
              onClick={handleTestWhatsApp}
              disabled={testingWa || !form.whatsapp_instance_id}
              className="text-xs"
            >
              <TestTube size={14} className="mr-1" />
              {testingWa ? 'Enviando...' : 'Enviar mensaje de prueba'}
            </Button>
          </div>
        </Card>
      </div>

      {/* Herramientas del agente */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={20} className="text-warning" />
          <h2 className="text-lg font-semibold">Herramientas del agente</h2>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Selecciona que herramientas puede usar el agente de voz durante las llamadas.
        </p>
        <div className="space-y-3">
          {allTools.map(tool => {
            const enabled = form.enabled_tools.includes(tool.key)
            return (
              <label
                key={tool.key}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  enabled
                    ? 'border-accent/30 bg-accent/5'
                    : 'border-border bg-bg-primary hover:bg-bg-hover'
                }`}
              >
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => toggleTool(tool.key)}
                  className="sr-only"
                />
                <div className={`w-5 h-5 rounded flex items-center justify-center ${
                  enabled ? 'bg-accent text-black' : 'bg-bg-hover border border-border'
                }`}>
                  {enabled && <Check size={12} />}
                </div>
                <div>
                  <p className="text-sm font-medium">{tool.label}</p>
                  <p className="text-xs text-text-muted">{tool.desc}</p>
                </div>
              </label>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
