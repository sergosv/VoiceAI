import { useEffect, useState, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Save, Volume2, Zap, RefreshCw, Eye, FileText, Bot, Plus, Trash2, Mic,
  Brain, Key, ChevronDown, ChevronUp, Check, Phone, MessageCircle, Settings2,
  Shield, Globe, Star, Bell, Clock, Webhook,
} from 'lucide-react'
import HooksEditor from '../components/HooksEditor'
import InsightsPanel from '../components/InsightsPanel'
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
import { GHLConfig } from '../components/GHLConfig'
import { VoiceCloning } from '../components/VoiceCloning'

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

const GEMINI_LIVE_MODELS = [
  { value: 'gemini-3.1-flash-live-preview', label: 'Gemini 3.1 Flash Live (recomendado)' },
  { value: 'gemini-2.5-flash-native-audio-preview', label: 'Gemini 2.5 Flash Audio' },
]

const GEMINI_LIVE_VOICES = [
  { value: 'Puck', label: 'Puck', desc: 'Versatil, natural (default)' },
  { value: 'Charon', label: 'Charon', desc: 'Profunda, autoritativa' },
  { value: 'Kore', label: 'Kore', desc: 'Clara, profesional' },
  { value: 'Fenrir', label: 'Fenrir', desc: 'Firme, directa' },
  { value: 'Aoede', label: 'Aoede', desc: 'Calida, melodica' },
  { value: 'Leda', label: 'Leda', desc: 'Suave, amigable' },
  { value: 'Orus', label: 'Orus', desc: 'Energetica, clara' },
  { value: 'Zephyr', label: 'Zephyr', desc: 'Ligera, fresca' },
  { value: 'Schedar', label: 'Schedar', desc: 'Serena, confiable' },
  { value: 'Gacrux', label: 'Gacrux', desc: 'Resonante, segura' },
  { value: 'Umbriel', label: 'Umbriel', desc: 'Misteriosa, profunda' },
  { value: 'Algieba', label: 'Algieba', desc: 'Expresiva, dinamica' },
  { value: 'Sulafat', label: 'Sulafat', desc: 'Brillante, vivaz' },
  { value: 'Laomedeia', label: 'Laomedeia', desc: 'Sofisticada, elegante' },
  { value: 'Achernar', label: 'Achernar', desc: 'Neutra, balanceada' },
]

const GEMINI_LIVE_THINKING = [
  { value: 'minimal', label: 'Minimal — mas rapido' },
  { value: 'low', label: 'Low — balance rapido' },
  { value: 'medium', label: 'Medium — razonamiento medio' },
  { value: 'high', label: 'High — razonamiento profundo' },
]

const PROVIDER_LABELS = {
  cartesia: 'Cartesia',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI TTS',
}

const SERVICE_TABS = [
  { key: 'general', label: 'General', icon: Bot },
  { key: 'voice', label: 'Voz', icon: Volume2 },
  { key: 'calls', label: 'Llamadas', icon: Phone },
  { key: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { key: 'ghl', label: 'GoHighLevel', icon: Zap },
  { key: 'intelligence', label: 'Inteligencia', icon: Brain },
  { key: 'api', label: 'API', icon: Key },
  { key: 'widget', label: 'Widget', icon: Globe },
  { key: 'hooks', label: 'Reglas', icon: Webhook },
  { key: 'insights', label: 'Insights', icon: Brain },
  { key: 'advanced', label: 'Avanzado', icon: Settings2 },
]

const PA_TABS = [
  { key: 'general', label: 'General', icon: Bot },
  { key: 'voice', label: 'Voz', icon: Volume2 },
  { key: 'pa_callers', label: 'Numeros', icon: Phone },
  { key: 'pa_memory', label: 'Memoria', icon: Brain },
  { key: 'pa_tasks', label: 'Tareas', icon: Check },
  { key: 'pa_email', label: 'Email', icon: Globe },
  { key: 'calls', label: 'Llamadas', icon: Phone },
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

function ByotTwilioSection({ clientId, client, setClient }) {
  const [sid, setSid] = useState('')
  const [token, setToken] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const { addToast } = useToast()

  const hasCreds = client?.has_twilio_credentials

  const handleSave = async () => {
    if (!sid.startsWith('AC') || sid.length !== 34) {
      addToast('Account SID debe empezar con AC y tener 34 caracteres', 'error')
      return
    }
    if (token.length !== 32) {
      addToast('Auth Token debe tener 32 caracteres', 'error')
      return
    }
    setSaving(true)
    try {
      const res = await api.put(`/clients/${clientId}/twilio-credentials`, {
        account_sid: sid, auth_token: token,
      })
      setClient(res.data)
      setSid('')
      setToken('')
      addToast('Credenciales de Twilio verificadas y guardadas', 'success')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error guardando credenciales', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      const res = await api.delete(`/clients/${clientId}/twilio-credentials`)
      setClient(res.data)
      addToast('Credenciales de Twilio eliminadas', 'success')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error eliminando credenciales', 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Phone size={16} className="text-orange-400" />
        Twilio — Cuenta propia (BYOT)
      </h2>
      <p className="text-xs text-text-muted">
        Conecta tu propia cuenta de Twilio para usar tus numeros y pagar la telefonia directamente.
        Si no configuras esto, se usara la cuenta de la plataforma.
      </p>

      {hasCreds ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-sm">
            <Check size={14} className="text-success" />
            <span className="text-success">Cuenta Twilio conectada</span>
          </div>
          <Button variant="secondary" onClick={handleDelete} disabled={deleting} className="text-xs text-red-400 hover:text-red-300">
            {deleting ? 'Eliminando...' : 'Desconectar cuenta Twilio'}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <Input
            label="Account SID"
            value={sid}
            onChange={e => setSid(e.target.value.trim())}
            placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          />
          <Input
            label="Auth Token"
            type="password"
            value={token}
            onChange={e => setToken(e.target.value.trim())}
            placeholder="32 caracteres"
          />
          <Button onClick={handleSave} disabled={saving || !sid || !token}>
            {saving ? 'Verificando...' : 'Verificar y conectar'}
          </Button>
        </div>
      )}
    </Card>
  )
}


// ── PA Tab Components ──────────────────────────────────

function PaCallersTab({ agentId }) {
  const [callers, setCallers] = useState([])
  const [phone, setPhone] = useState('')
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()

  const load = async () => {
    try {
      const data = await api.get(`/agents/${agentId}/pa/callers`)
      setCallers(data)
    } catch (e) { addToast('Error cargando callers', 'error') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [agentId])

  const handleAdd = async () => {
    if (!phone) return
    try {
      await api.post(`/agents/${agentId}/pa/callers`, { phone_number: phone, label: label || null, is_owner: callers.length === 0 })
      setPhone(''); setLabel('')
      load()
      addToast('Numero autorizado agregado', 'success')
    } catch (e) { addToast(e.response?.data?.detail || 'Error', 'error') }
  }

  const handleRemove = async (id) => {
    await api.delete(`/agents/${agentId}/pa/callers/${id}`)
    load()
  }

  if (loading) return <Card className="p-6"><Spinner /></Card>

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Phone size={16} className="text-cyan-400" />
        Numeros autorizados
      </h2>
      <p className="text-xs text-text-muted">Solo estos numeros pueden hablar con tu asistente personal.</p>

      <div className="space-y-2">
        {callers.map(c => (
          <div key={c.id} className="flex items-center justify-between px-3 py-2 bg-bg-secondary rounded-lg">
            <div>
              <span className="font-mono text-sm">{c.phone_number}</span>
              {c.label && <span className="text-text-muted text-xs ml-2">({c.label})</span>}
              {c.is_owner && <span className="text-cyan-400 text-xs ml-2">Propietario</span>}
            </div>
            <button onClick={() => handleRemove(c.id)} className="text-red-400 text-xs hover:text-red-300 cursor-pointer">Eliminar</button>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Input placeholder="+52..." value={phone} onChange={e => setPhone(e.target.value)} className="flex-1" />
        <Input placeholder="Etiqueta (opcional)" value={label} onChange={e => setLabel(e.target.value)} className="w-40" />
        <Button onClick={handleAdd} disabled={!phone}>Agregar</Button>
      </div>
    </Card>
  )
}

function PaMemoryTab({ agentId }) {
  const [items, setItems] = useState([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '50' })
      if (filter) params.set('item_type', filter)
      if (search) params.set('q', search)
      const data = await api.get(`/agents/${agentId}/pa/memory?${params}`)
      setItems(data)
    } catch (e) { addToast('Error cargando memoria', 'error') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [agentId, filter])

  const handleDelete = async (id) => {
    await api.delete(`/agents/${agentId}/pa/memory/${id}`)
    setItems(items.filter(i => i.id !== id))
  }

  const TYPE_LABELS = { fact: 'Dato', preference: 'Preferencia', task: 'Tarea', note: 'Nota', reminder: 'Recordatorio' }
  const TYPE_COLORS = { fact: 'text-blue-400', preference: 'text-purple-400', task: 'text-yellow-400', note: 'text-green-400', reminder: 'text-orange-400' }

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Brain size={16} className="text-cyan-400" />
        Memoria del asistente
      </h2>

      <div className="flex gap-2">
        <Input placeholder="Buscar en memoria..." value={search} onChange={e => setSearch(e.target.value)} className="flex-1" />
        <Button onClick={load} variant="secondary">Buscar</Button>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          className="px-3 py-1.5 bg-bg-secondary border border-border rounded-lg text-sm">
          <option value="">Todos</option>
          <option value="fact">Datos</option>
          <option value="preference">Preferencias</option>
          <option value="note">Notas</option>
          <option value="reminder">Recordatorios</option>
        </select>
      </div>

      {loading ? <Spinner /> : (
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {items.length === 0 && <p className="text-text-muted text-sm py-4 text-center">Sin items en memoria</p>}
          {items.map(item => (
            <div key={item.id} className="flex items-start justify-between px-3 py-2 bg-bg-secondary rounded-lg">
              <div className="flex-1">
                <span className={`text-xs font-medium ${TYPE_COLORS[item.item_type] || 'text-text-muted'}`}>
                  {TYPE_LABELS[item.item_type] || item.item_type}
                </span>
                <p className="text-sm mt-0.5">{item.content}</p>
              </div>
              <button onClick={() => handleDelete(item.id)} className="text-red-400/50 text-xs hover:text-red-400 ml-2 shrink-0 cursor-pointer">x</button>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function PaTasksTab({ agentId }) {
  const [tasks, setTasks] = useState([])
  const [showCompleted, setShowCompleted] = useState(false)
  const [loading, setLoading] = useState(true)
  const { addToast } = useToast()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api.get(`/agents/${agentId}/pa/tasks?completed=${showCompleted}`)
      setTasks(data)
    } catch (e) { addToast('Error cargando tareas', 'error') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [agentId, showCompleted])

  const toggleComplete = async (task) => {
    try {
      await api.patch(`/agents/${agentId}/pa/tasks/${task.id}`, { is_completed: !task.is_completed })
      load()
    } catch (e) { addToast('Error actualizando tarea', 'error') }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
          <Check size={16} className="text-cyan-400" />
          Tareas
        </h2>
        <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer">
          <input type="checkbox" checked={showCompleted} onChange={e => setShowCompleted(e.target.checked)} className="accent-cyan-400" />
          Mostrar completadas
        </label>
      </div>

      {loading ? <Spinner /> : (
        <div className="space-y-1">
          {tasks.length === 0 && <p className="text-text-muted text-sm py-4 text-center">Sin tareas</p>}
          {tasks.map(t => (
            <div key={t.id} className="flex items-center gap-3 px-3 py-2 bg-bg-secondary rounded-lg">
              <button onClick={() => toggleComplete(t)}
                className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 cursor-pointer ${t.is_completed ? 'bg-cyan-500 border-cyan-500' : 'border-border hover:border-cyan-400'}`}>
                {t.is_completed && <Check size={12} className="text-white" />}
              </button>
              <span className={`text-sm flex-1 ${t.is_completed ? 'line-through text-text-muted' : ''}`}>{t.content}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function PaEmailTab({ agentId }) {
  const [config, setConfig] = useState({ from_name: '', from_email: '', reply_to: '', signature: '' })
  const [hasConfig, setHasConfig] = useState(false)
  const [saving, setSaving] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    api.get(`/agents/${agentId}/pa/email-config`).then(data => {
      if (data) { setConfig(data); setHasConfig(true) }
    }).catch(() => {})
  }, [agentId])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await api.put(`/agents/${agentId}/pa/email-config`, config)
      setConfig(res); setHasConfig(true)
      addToast('Configuracion de email guardada', 'success')
    } catch (e) { addToast(e.response?.data?.detail || 'Error', 'error') }
    finally { setSaving(false) }
  }

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Globe size={16} className="text-cyan-400" />
        Configuracion de email
      </h2>
      <p className="text-xs text-text-muted">Configura como se envian los emails desde tu asistente.</p>

      <Input label="Nombre del remitente" placeholder="Asistente de Dr. Garcia"
        value={config.from_name} onChange={e => setConfig(c => ({ ...c, from_name: e.target.value }))} />
      <Input label="Email del remitente" placeholder="asistente@tudominio.com"
        value={config.from_email} onChange={e => setConfig(c => ({ ...c, from_email: e.target.value }))} />
      <Input label="Reply-to (tu email real)" placeholder="tu@email.com"
        value={config.reply_to || ''} onChange={e => setConfig(c => ({ ...c, reply_to: e.target.value }))} />
      <Textarea label="Firma del email" rows={3} placeholder="--\nDr. Garcia\nClinica Dental\nTel: +52..."
        value={config.signature || ''} onChange={e => setConfig(c => ({ ...c, signature: e.target.value }))} />

      <Button onClick={handleSave} disabled={saving || !config.from_name || !config.from_email}>
        <Save size={16} className="mr-2 inline" />
        {saving ? 'Guardando...' : 'Guardar configuracion'}
      </Button>
    </Card>
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

/* ─────────────────── Intelligence Tab Component ─────────────────── */

const RULE_TYPES = [
  { value: 'callback_missed_call', label: 'Callback llamada perdida' },
  { value: 'followup_no_conversion', label: 'Seguimiento sin conversion' },
  { value: 'reminder_appointment', label: 'Recordatorio de cita' },
  { value: 'post_sale', label: 'Post-venta' },
  { value: 'reengagement', label: 'Reengagement' },
  { value: 'custom', label: 'Personalizado' },
]

const SUPPORTED_LANGUAGES = [
  { code: 'es', label: 'Espanol' },
  { code: 'en', label: 'English' },
  { code: 'pt', label: 'Portugues' },
  { code: 'fr', label: 'Francais' },
]

const DAYS_OF_WEEK = [
  { key: 'monday', label: 'Lunes' },
  { key: 'tuesday', label: 'Martes' },
  { key: 'wednesday', label: 'Miercoles' },
  { key: 'thursday', label: 'Jueves' },
  { key: 'friday', label: 'Viernes' },
  { key: 'saturday', label: 'Sabado' },
  { key: 'sunday', label: 'Domingo' },
]

const DEFAULT_HOURS = { open: '09:00', close: '18:00' }

function BusinessHoursEditor({ value, onChange }) {
  const enabled = !!value
  const hours = value || {}

  function toggleEnabled() {
    onChange(enabled ? null : {
      monday: { ...DEFAULT_HOURS },
      tuesday: { ...DEFAULT_HOURS },
      wednesday: { ...DEFAULT_HOURS },
      thursday: { ...DEFAULT_HOURS },
      friday: { ...DEFAULT_HOURS },
      saturday: null,
      sunday: null,
    })
  }

  function toggleDay(dayKey) {
    const updated = { ...hours }
    updated[dayKey] = updated[dayKey] ? null : { ...DEFAULT_HOURS }
    onChange(updated)
  }

  function updateTime(dayKey, field, val) {
    const updated = { ...hours }
    updated[dayKey] = { ...updated[dayKey], [field]: val }
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={16} className="text-accent" />
          <span className="text-sm font-medium">Horario de atencion</span>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" className="sr-only peer" checked={enabled} onChange={toggleEnabled} />
          <div className="w-9 h-5 bg-bg-hover rounded-full peer peer-checked:bg-accent/80 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" />
        </label>
      </div>
      {enabled && (
        <div className="space-y-2">
          <p className="text-xs text-text-muted">
            Define los horarios en que el agente esta disponible. Fuera de horario se reproduce el mensaje configurado.
          </p>
          {DAYS_OF_WEEK.map(({ key, label }) => {
            const dayHours = hours[key]
            const isOpen = !!dayHours
            return (
              <div key={key} className="flex items-center gap-3 py-1.5">
                <label className="relative inline-flex items-center cursor-pointer shrink-0">
                  <input type="checkbox" className="sr-only peer" checked={isOpen} onChange={() => toggleDay(key)} />
                  <div className="w-8 h-4 bg-bg-hover rounded-full peer peer-checked:bg-accent/80 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-4" />
                </label>
                <span className={`text-sm w-24 ${isOpen ? 'text-text-primary' : 'text-text-muted'}`}>{label}</span>
                {isOpen ? (
                  <div className="flex items-center gap-2 text-xs">
                    <input
                      type="time"
                      value={dayHours.open}
                      onChange={e => updateTime(key, 'open', e.target.value)}
                      className="bg-bg-primary border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent"
                    />
                    <span className="text-text-muted">a</span>
                    <input
                      type="time"
                      value={dayHours.close}
                      onChange={e => updateTime(key, 'close', e.target.value)}
                      className="bg-bg-primary border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent"
                    />
                  </div>
                ) : (
                  <span className="text-xs text-text-muted">Cerrado</span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function ToggleSwitch({ checked, onChange }) {
  return (
    <label className="relative inline-flex items-center cursor-pointer">
      <input type="checkbox" className="sr-only peer" checked={checked} onChange={e => onChange(e.target.checked)} />
      <div className="w-9 h-5 bg-bg-hover rounded-full peer peer-checked:bg-accent/80 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" />
    </label>
  )
}

function IntelligenceSectionCard({ icon: Icon, iconColor, title, description, enabled, onToggle, children }) {
  return (
    <Card className="space-y-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon size={16} className={iconColor} />
          <h2 className="text-sm font-semibold text-text-secondary">{title}</h2>
        </div>
        <ToggleSwitch checked={enabled} onChange={onToggle} />
      </div>
      {description && (
        <p className="text-xs text-text-muted mt-1">{description}</p>
      )}
      {enabled && (
        <div className="mt-4 space-y-4">
          {children}
        </div>
      )}
    </Card>
  )
}

function IntelligenceTab({ form, setForm }) {
  // Config updater helpers
  function updateConfig(configKey, defaults) {
    return (key, value) => {
      setForm(f => ({
        ...f,
        [configKey]: { ...(f[configKey] || { enabled: false, ...defaults }), [key]: value },
      }))
    }
  }

  const updateSentiment = updateConfig('sentiment_config', { escalation_threshold: 3, auto_transfer: false, notify_on_negative: false })
  const updateIntent = updateConfig('intent_config', { custom_intents: '', track_unresolved: true })
  const updateGuardrails = updateConfig('guardrails_config', { prohibited_topics: '', blocked_patterns: '', max_response_length: '', detect_prompt_injection: true })
  const updateLanguage = updateConfig('language_detection_config', { supported_languages: ['es'], detection_turns: 2 })
  const updateQuality = updateConfig('quality_config', { min_score_alert: 50 })
  const updateProactive = updateConfig('proactive_config', { rules: [] })

  const sc = form.sentiment_config || {}
  const ic = form.intent_config || {}
  const gc = form.guardrails_config || {}
  const ldc = form.language_detection_config || {}
  const qc = form.quality_config || {}
  const pc = form.proactive_config || {}

  function addProactiveRule() {
    const newRule = { type: 'callback_missed_call', delay_minutes: 5, channel: 'call', message: '', max_attempts: 1 }
    const currentRules = pc.rules || []
    updateProactive('rules', [...currentRules, newRule])
  }

  function updateRule(index, key, value) {
    const rules = [...(pc.rules || [])]
    rules[index] = { ...rules[index], [key]: value }
    updateProactive('rules', rules)
  }

  function removeRule(index) {
    const rules = [...(pc.rules || [])]
    rules.splice(index, 1)
    updateProactive('rules', rules)
  }

  function toggleLanguage(code) {
    const current = ldc.supported_languages || ['es']
    const next = current.includes(code) ? current.filter(c => c !== code) : [...current, code]
    if (next.length === 0) return // Al menos uno
    updateLanguage('supported_languages', next)
  }

  return (
    <div className="space-y-6">
      {/* ── Sentimiento en Tiempo Real ── */}
      <IntelligenceSectionCard
        icon={Brain}
        iconColor="text-pink-400"
        title="Sentimiento en Tiempo Real"
        description="Detecta emociones negativas durante la llamada y reacciona automaticamente."
        enabled={sc.enabled || false}
        onToggle={v => updateSentiment('enabled', v)}
      >
        <Input
          label="Umbral de escalacion (1-10)"
          type="number"
          min={1}
          max={10}
          value={sc.escalation_threshold ?? 3}
          onChange={e => updateSentiment('escalation_threshold', parseInt(e.target.value) || 3)}
        />
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={sc.auto_transfer || false}
            onChange={e => updateSentiment('auto_transfer', e.target.checked)}
            className="rounded border-border bg-bg-primary text-accent focus:ring-accent"
          />
          Transferir automaticamente al detectar sentimiento critico
        </label>
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={sc.notify_on_negative || false}
            onChange={e => updateSentiment('notify_on_negative', e.target.checked)}
            className="rounded border-border bg-bg-primary text-accent focus:ring-accent"
          />
          Notificar al detectar sentimiento negativo
        </label>
      </IntelligenceSectionCard>

      {/* ── Intent Extraction ── */}
      <IntelligenceSectionCard
        icon={Zap}
        iconColor="text-yellow-400"
        title="Extraccion de Intenciones"
        description="Identifica automaticamente la intencion del usuario en cada mensaje."
        enabled={ic.enabled || false}
        onToggle={v => updateIntent('enabled', v)}
      >
        <Textarea
          label="Intenciones personalizadas (separadas por coma)"
          placeholder="cotizacion, soporte tecnico, reclamacion"
          value={ic.custom_intents || ''}
          onChange={e => updateIntent('custom_intents', e.target.value)}
          rows={3}
        />
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={ic.track_unresolved !== false}
            onChange={e => updateIntent('track_unresolved', e.target.checked)}
            className="rounded border-border bg-bg-primary text-accent focus:ring-accent"
          />
          Rastrear intenciones no resueltas
        </label>
      </IntelligenceSectionCard>

      {/* ── Guardrails ── */}
      <IntelligenceSectionCard
        icon={Shield}
        iconColor="text-red-400"
        title="Guardrails"
        description="Protege al agente de temas prohibidos, inyeccion de prompts y respuestas largas."
        enabled={gc.enabled || false}
        onToggle={v => updateGuardrails('enabled', v)}
      >
        <Textarea
          label="Temas prohibidos (uno por linea)"
          placeholder={"precio competencia\ninformacion confidencial"}
          value={gc.prohibited_topics || ''}
          onChange={e => updateGuardrails('prohibited_topics', e.target.value)}
          rows={3}
        />
        <Textarea
          label="Patrones bloqueados (regex, uno por linea)"
          placeholder={"\\b(contraseña|password)\\b\n\\d{16}"}
          value={gc.blocked_patterns || ''}
          onChange={e => updateGuardrails('blocked_patterns', e.target.value)}
          rows={3}
        />
        <Input
          label="Longitud maxima de respuesta (caracteres, opcional)"
          type="number"
          min={0}
          value={gc.max_response_length || ''}
          onChange={e => updateGuardrails('max_response_length', e.target.value ? parseInt(e.target.value) : '')}
          placeholder="Sin limite"
        />
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={gc.detect_prompt_injection !== false}
            onChange={e => updateGuardrails('detect_prompt_injection', e.target.checked)}
            className="rounded border-border bg-bg-primary text-accent focus:ring-accent"
          />
          Detectar inyeccion de prompts
        </label>
      </IntelligenceSectionCard>

      {/* ── Deteccion de Idioma ── */}
      <IntelligenceSectionCard
        icon={Globe}
        iconColor="text-blue-400"
        title="Deteccion de Idioma"
        description="Detecta el idioma del usuario y adapta las respuestas automaticamente."
        enabled={ldc.enabled || false}
        onToggle={v => updateLanguage('enabled', v)}
      >
        <div>
          <label className="block text-xs text-text-muted mb-2">Idiomas soportados</label>
          <div className="flex flex-wrap gap-2">
            {SUPPORTED_LANGUAGES.map(lang => {
              const active = (ldc.supported_languages || ['es']).includes(lang.code)
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => toggleLanguage(lang.code)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    active
                      ? 'bg-accent/20 text-accent border border-accent/40'
                      : 'bg-bg-hover text-text-muted border border-border hover:border-text-muted'
                  }`}
                >
                  {lang.label}
                </button>
              )
            })}
          </div>
        </div>
        <Input
          label="Turnos para deteccion (1-5)"
          type="number"
          min={1}
          max={5}
          value={ldc.detection_turns ?? 2}
          onChange={e => updateLanguage('detection_turns', parseInt(e.target.value) || 2)}
        />
      </IntelligenceSectionCard>

      {/* ── Quality Scoring ── */}
      <IntelligenceSectionCard
        icon={Star}
        iconColor="text-amber-400"
        title="Quality Scoring"
        description="Evalua automaticamente la calidad de cada interaccion."
        enabled={qc.enabled || false}
        onToggle={v => updateQuality('enabled', v)}
      >
        <Input
          label="Score minimo para alerta (0-100)"
          type="number"
          min={0}
          max={100}
          value={qc.min_score_alert ?? 50}
          onChange={e => updateQuality('min_score_alert', parseInt(e.target.value) || 50)}
        />
      </IntelligenceSectionCard>

      {/* ── Agente Proactivo ── */}
      <IntelligenceSectionCard
        icon={Bell}
        iconColor="text-green-400"
        title="Agente Proactivo"
        description="Define reglas para que el agente contacte proactivamente a los usuarios."
        enabled={pc.enabled || false}
        onToggle={v => updateProactive('enabled', v)}
      >
        {(pc.rules || []).map((rule, i) => (
          <Card key={i} className="space-y-3 !bg-bg-primary border-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-text-secondary">Regla {i + 1}</span>
              <button
                type="button"
                onClick={() => removeRule(i)}
                className="text-red-400 hover:text-red-300 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Select
                label="Tipo"
                value={rule.type}
                onChange={e => updateRule(i, 'type', e.target.value)}
                options={RULE_TYPES}
              />
              <Select
                label="Canal"
                value={rule.channel}
                onChange={e => updateRule(i, 'channel', e.target.value)}
                options={[
                  { value: 'call', label: 'Llamada' },
                  { value: 'whatsapp', label: 'WhatsApp' },
                ]}
              />
              <Input
                label="Retraso (minutos)"
                type="number"
                min={0}
                value={rule.delay_minutes ?? 5}
                onChange={e => updateRule(i, 'delay_minutes', parseInt(e.target.value) || 0)}
              />
              <Input
                label="Intentos maximos"
                type="number"
                min={1}
                value={rule.max_attempts ?? 1}
                onChange={e => updateRule(i, 'max_attempts', parseInt(e.target.value) || 1)}
              />
            </div>
            <Textarea
              label="Mensaje"
              placeholder="Hola, te estamos contactando porque..."
              value={rule.message || ''}
              onChange={e => updateRule(i, 'message', e.target.value)}
              rows={2}
            />
          </Card>
        ))}
        <Button variant="secondary" onClick={addProactiveRule} className="w-full">
          <Plus size={14} className="mr-1" /> Agregar regla
        </Button>
      </IntelligenceSectionCard>
    </div>
  )
}

/* ─────────────────────── API Keys Panel ─────────────────────────── */

function ApiKeysPanel({ clientId }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyScopes, setNewKeyScopes] = useState('')
  const [createdKey, setCreatedKey] = useState(null)
  const toast = useToast()

  const loadKeys = useCallback(async () => {
    try {
      const data = await api.get(`/api-keys/${clientId}`)
      setKeys(data)
    } catch { /* ignore */ }
    setLoading(false)
  }, [clientId])

  useEffect(() => { loadKeys() }, [loadKeys])

  async function handleCreate() {
    if (!newKeyName.trim()) return
    setCreating(true)
    try {
      const scopes = newKeyScopes.trim() ? newKeyScopes.split(',').map(s => s.trim()) : []
      const result = await api.post(`/api-keys/${clientId}`, { name: newKeyName, scopes })
      setCreatedKey(result.key)
      setNewKeyName('')
      setNewKeyScopes('')
      toast.success('API key creada. Copia la key ahora — no se volvera a mostrar.')
      await loadKeys()
    } catch (e) {
      toast.error(e.message || 'Error creando API key')
    }
    setCreating(false)
  }

  async function handleRevoke(id) {
    try {
      await api.post(`/api-keys/${clientId}/${id}/revoke`)
      toast.success('API key revocada')
      await loadKeys()
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleDelete(id) {
    try {
      await api.delete(`/api-keys/${clientId}/${id}`)
      toast.success('API key eliminada')
      await loadKeys()
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Key size={16} className="text-accent" />
        API Keys
      </h2>
      <p className="text-xs text-text-muted">
        Crea keys para acceder a la Public API (endpoints /api/v1/). Cada key se muestra solo una vez al crearla.
      </p>

      {/* Crear key */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newKeyName}
          onChange={e => setNewKeyName(e.target.value)}
          placeholder="Nombre de la key"
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
        />
        <input
          type="text"
          value={newKeyScopes}
          onChange={e => setNewKeyScopes(e.target.value)}
          placeholder="Scopes (ej: calls:read,contacts:read)"
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-accent/50"
        />
        <Button onClick={handleCreate} disabled={creating || !newKeyName.trim()}>
          {creating ? <Spinner size={14} /> : <Plus size={14} />}
          <span className="ml-1">Crear</span>
        </Button>
      </div>

      {/* Key recien creada */}
      {createdKey && (
        <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1">
          <p className="text-xs text-green-400 font-medium">Tu nueva API key (copiala ahora):</p>
          <code className="block text-xs bg-bg-primary rounded px-2 py-1 font-mono break-all select-all">{createdKey}</code>
          <button onClick={() => { navigator.clipboard.writeText(createdKey); toast('Copiada!', 'success') }}
            className="text-xs text-accent hover:underline cursor-pointer">Copiar al portapapeles</button>
        </div>
      )}

      {/* Lista */}
      {loading ? <Spinner /> : keys.length === 0 ? (
        <p className="text-xs text-text-muted py-2">No hay API keys.</p>
      ) : (
        <div className="space-y-2">
          {keys.map(k => (
            <div key={k.id} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-border bg-bg-primary/50">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium">{k.name}</span>
                <span className="text-xs text-text-muted ml-2">{k.key_prefix}...</span>
                {!k.is_active && <span className="text-xs text-red-400 ml-2">Revocada</span>}
                {k.scopes?.length > 0 && (
                  <span className="text-[10px] text-text-muted ml-2">[{k.scopes.join(', ')}]</span>
                )}
              </div>
              <span className="text-[10px] text-text-muted">{k.last_used_at ? `Usado: ${new Date(k.last_used_at).toLocaleDateString()}` : 'Sin uso'}</span>
              {k.is_active && (
                <button onClick={() => handleRevoke(k.id)} className="text-xs text-yellow-400 hover:underline cursor-pointer">Revocar</button>
              )}
              <button onClick={() => handleDelete(k.id)} className="text-xs text-red-400 hover:underline cursor-pointer">Eliminar</button>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ─────────────────────── Webhooks Panel ─────────────────────────── */

function WebhooksPanel({ clientId }) {
  const [endpoints, setEndpoints] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [newEvents, setNewEvents] = useState('')
  const [createdSecret, setCreatedSecret] = useState(null)
  const toast = useToast()

  const loadEndpoints = useCallback(async () => {
    try {
      const data = await api.get(`/webhook-endpoints/${clientId}`)
      setEndpoints(data)
    } catch { /* ignore */ }
    setLoading(false)
  }, [clientId])

  useEffect(() => { loadEndpoints() }, [loadEndpoints])

  async function handleCreate() {
    if (!newUrl.trim() || !newEvents.trim()) return
    setCreating(true)
    try {
      const events = newEvents.split(',').map(s => s.trim())
      const result = await api.post(`/webhook-endpoints/${clientId}`, { url: newUrl, events })
      setCreatedSecret(result.secret)
      setNewUrl('')
      setNewEvents('')
      toast.success('Webhook creado. Copia el secret para verificar las firmas.')
      await loadEndpoints()
    } catch (e) {
      toast.error(e.message || 'Error creando webhook')
    }
    setCreating(false)
  }

  async function handleDelete(id) {
    try {
      await api.delete(`/webhook-endpoints/${clientId}/${id}`)
      toast.success('Webhook eliminado')
      await loadEndpoints()
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleToggle(ep) {
    try {
      await api.patch(`/webhook-endpoints/${clientId}/${ep.id}`, { is_active: !ep.is_active })
      await loadEndpoints()
    } catch (e) {
      toast.error(e.message)
    }
  }

  return (
    <Card className="space-y-4">
      <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
        <Bell size={16} className="text-accent" />
        Webhooks
      </h2>
      <p className="text-xs text-text-muted">
        Recibe notificaciones HTTP cuando ocurran eventos (call.completed, contact.created, etc.).
        Cada entrega incluye una firma HMAC-SHA256 en el header X-Webhook-Signature.
      </p>

      {/* Crear webhook */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newUrl}
          onChange={e => setNewUrl(e.target.value)}
          placeholder="https://tu-servidor.com/webhook"
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50"
        />
        <input
          type="text"
          value={newEvents}
          onChange={e => setNewEvents(e.target.value)}
          placeholder="Eventos (ej: call.*,contact.created)"
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-accent/50"
        />
        <Button onClick={handleCreate} disabled={creating || !newUrl.trim() || !newEvents.trim()}>
          {creating ? <Spinner size={14} /> : <Plus size={14} />}
          <span className="ml-1">Crear</span>
        </Button>
      </div>

      {/* Secret recién creado */}
      {createdSecret && (
        <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1">
          <p className="text-xs text-green-400 font-medium">Webhook secret (cópialo ahora):</p>
          <code className="block text-xs bg-bg-primary rounded px-2 py-1 font-mono break-all select-all">{createdSecret}</code>
          <button onClick={() => { navigator.clipboard.writeText(createdSecret); toast('Copiado!', 'success') }}
            className="text-xs text-accent hover:underline cursor-pointer">Copiar al portapapeles</button>
        </div>
      )}

      {/* Lista */}
      {loading ? <Spinner /> : endpoints.length === 0 ? (
        <p className="text-xs text-text-muted py-2">No hay webhooks configurados.</p>
      ) : (
        <div className="space-y-2">
          {endpoints.map(ep => (
            <div key={ep.id} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-border bg-bg-primary/50">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium truncate block">{ep.url}</span>
                <span className="text-[10px] text-text-muted">{(ep.events || []).join(', ')}</span>
                {ep.description && <span className="text-[10px] text-text-muted ml-2">— {ep.description}</span>}
              </div>
              <button onClick={() => handleToggle(ep)}
                className={`text-xs cursor-pointer ${ep.is_active ? 'text-green-400' : 'text-red-400'}`}>
                {ep.is_active ? 'Activo' : 'Inactivo'}
              </button>
              <button onClick={() => handleDelete(ep.id)} className="text-xs text-red-400 hover:underline cursor-pointer">Eliminar</button>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/* ─────────────────────── Main Component ─────────────────────────── */

export function Settings() {
  const { agentId: urlAgentId } = useParams()
  const { user, impersonatingClientId } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  /* ── State ── */
  const [client, setClient] = useState(null)
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [voices, setVoices] = useState([])
  const [clonedVoices, setClonedVoices] = useState([])
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
    after_hours_message: '', business_hours: null, conversation_mode: 'prompt', max_call_duration_seconds: 300,
    transfer_number: '', is_active: true,
    agent_mode: 'pipeline', stt_provider: 'deepgram', llm_provider: 'google', tts_provider: 'cartesia',
    stt_api_key: '', llm_api_key: '', tts_api_key: '', realtime_api_key: '',
    realtime_voice: 'alloy', realtime_model: 'gpt-4o-realtime-preview', voice_id: '',
    gemini_live_model: 'gemini-3.1-flash-live-preview', gemini_live_voice: 'Puck',
    gemini_live_thinking_level: 'minimal',
    role_description: '', orchestrator_enabled: true, orchestrator_priority: 0,
    mode_config: {},
    conversation_flow: null,
    sentiment_config: null, intent_config: null, guardrails_config: null,
    language_detection_config: null, quality_config: null, proactive_config: null,
  })

  // Track server-side API key existence
  const [serverKeys, setServerKeys] = useState({
    has_stt_api_key: false,
    has_llm_api_key: false,
    has_tts_api_key: false,
    has_realtime_api_key: false,
  })

  const clientId = client?.id || impersonatingClientId || user?.client_id

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
      business_hours: agentData.business_hours || null,
      conversation_mode: agentData.conversation_mode || 'prompt',
      conversation_flow: agentData.conversation_flow || null,
      mode_config: agentData.mode_config || {},
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
      gemini_live_model: vc.gemini_live_model || 'gemini-3.1-flash-live-preview',
      gemini_live_voice: vc.gemini_live_voice || 'Puck',
      gemini_live_thinking_level: vc.gemini_live_thinking_level || 'minimal',
      role_description: agentData.role_description || '',
      orchestrator_enabled: agentData.orchestrator_enabled !== false,
      orchestrator_priority: agentData.orchestrator_priority || 0,
      sentiment_config: agentData.sentiment_config || null,
      intent_config: agentData.intent_config || null,
      guardrails_config: agentData.guardrails_config || null,
      language_detection_config: agentData.language_detection_config || null,
      quality_config: agentData.quality_config || null,
      proactive_config: agentData.proactive_config || null,
    })
    setServerKeys({
      has_stt_api_key: sc.has_api_key || false,
      has_llm_api_key: lc.has_api_key || false,
      has_tts_api_key: vc.has_api_key || false,
      has_realtime_api_key: vc.has_realtime_api_key || false,
    })
  }

  /* ── Voice loading ── */
  async function loadVoicesForAgent(agentData, cid, providerOverride) {
    const vc = agentData?.voice_config || {}
    const provider = providerOverride || vc.provider || 'cartesia'
    const mode = agentData?.agent_mode || 'pipeline'

    if ((mode === 'realtime' || mode === 'gemini_live') && !providerOverride) {
      setVoices([])
      return
    }

    setLoadingVoices(true)
    try {
      if (provider === 'elevenlabs' || provider === 'openai') {
        // Solo intentar cargar voces BYOK si hay key guardada en el servidor
        const vc = agentData?.voice_config || {}
        const hasKey = vc.has_api_key || false
        if (!hasKey) {
          // Sin key guardada — mostrar placeholder, no fallback a Cartesia
          setVoices([])
          setLoadingVoices(false)
          return
        }
        const v = await api.get(`/voices/provider/${cid}?agent_id=${agentData.id}&provider=${provider}`)
        setVoices(v)
      } else {
        const v = await api.get('/voices')
        setVoices(v)
      }
    } catch (err) {
      console.error('Error cargando voces:', err)
      setVoices([])
    } finally {
      setLoadingVoices(false)
    }
  }

  /* Recargar voces cuando cambia el TTS provider en el form */
  useEffect(() => {
    if (!selectedAgent || !clientId) return
    loadVoicesForAgent(selectedAgent, clientId, form.tts_provider)
  }, [form.tts_provider]) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Select an agent ── */
  function selectAgent(agent, cid) {
    // Limpiar widget preview anterior al cambiar de agente
    if (window.__voiceAIWidget) {
      const script = document.getElementById('vai-preview-script')
      if (script) script.remove()
      document.querySelectorAll('.vai-fab, .vai-tooltip, .vai-status, .vai-mode-menu, .vai-chat-panel, #vai-audio').forEach(el => el.remove())
      document.querySelectorAll('style').forEach(s => {
        if (s.textContent?.includes('vai-fab')) s.remove()
      })
      window.__voiceAIWidget = false
    }
    setSelectedAgent(agent)
    populateForm(agent)
    loadVoicesForAgent(agent, cid)
    // Cargar voces clonadas del cliente
    api.get(`/voices/cloned/${cid}`).then(setClonedVoices).catch(() => setClonedVoices([]))
  }

  /* ── Initial data load ── */
  useEffect(() => {
    if (user?.role === 'admin' && !impersonatingClientId) return setLoading(false)
    const effectiveClientId = impersonatingClientId || user?.client_id
    if (!effectiveClientId) return setLoading(false)

    const cid = effectiveClientId
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
      .catch(err => toast.error(err.message))
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
        business_hours: form.business_hours,
        max_call_duration_seconds: form.max_call_duration_seconds,
        is_active: form.is_active,
        voice_id: form.voice_id || null,
        stt_provider: form.stt_provider,
        llm_provider: form.llm_provider,
        tts_provider: form.tts_provider,
        realtime_voice: form.realtime_voice,
        realtime_model: form.realtime_model,
        gemini_live_model: form.gemini_live_model,
        gemini_live_voice: form.gemini_live_voice,
        gemini_live_thinking_level: form.gemini_live_thinking_level,
        role_description: form.role_description || null,
        orchestrator_enabled: form.orchestrator_enabled,
        orchestrator_priority: form.orchestrator_priority,
        conversation_mode: form.conversation_mode,
        conversation_flow: form.conversation_flow || null,
        mode_config: form.mode_config || {},
        sentiment_config: form.sentiment_config,
        intent_config: form.intent_config,
        guardrails_config: form.guardrails_config,
        language_detection_config: form.language_detection_config,
        quality_config: form.quality_config,
        proactive_config: form.proactive_config,
        widget_channels: selectedAgent.widget_channels || ['voice'],
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

      // Recargar voces si se guardó una API key de TTS (ej: ElevenLabs)
      if (form.tts_api_key && (form.tts_provider === 'elevenlabs' || form.tts_provider === 'openai')) {
        loadVoicesForAgent(updated, clientId, form.tts_provider)
      }

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

    // Voces clonadas primero (solo para Cartesia)
    if (form.tts_provider === 'cartesia' && clonedVoices.length > 0) {
      groups['Mis voces clonadas'] = clonedVoices.map(cv => ({
        key: cv.external_voice_id,
        id: cv.external_voice_id,
        name: `${cv.name} (clonada)`,
        language: cv.language,
        gender: 'cloned',
        description: cv.description || 'Voz clonada',
      }))
    }

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
  }, [filteredVoices, clonedVoices, form.tts_provider, client?.language])

  const currentVoice = voices?.find(v => v.id === form.voice_id)

  const isPipeline = form.agent_mode === 'pipeline'
  const isGeminiLive = form.agent_mode === 'gemini_live'

  /* ─────────────────────── Render: Loading ─────────────────────── */

  if (loading) return <PageLoader />

  /* ─────────────────────── Render: Admin redirect ──────────────── */

  if (user?.role === 'admin' && !impersonatingClientId) {
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
            {agent.agent_category === 'personal_assistant' && (
              <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-medium">PA</span>
            )}
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
            {(selectedAgent?.agent_category === 'personal_assistant' ? PA_TABS : SERVICE_TABS).map(tab => {
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
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'prompt', label: 'Prompt libre' },
                        { value: 'flow', label: 'Flujo visual' },
                        { value: 'survey', label: 'Encuesta' },
                        { value: 'quiz', label: 'Quiz' },
                        { value: 'negotiation', label: 'Negociacion' },
                        { value: 'interview', label: 'Entrevista' },
                      ].map(m => (
                        <button
                          key={m.value}
                          type="button"
                          onClick={() => setForm(f => ({ ...f, conversation_mode: m.value }))}
                          className={`px-3 py-2 rounded-lg text-xs border transition-colors cursor-pointer ${
                            form.conversation_mode === m.value
                              ? 'border-accent bg-accent/10 text-accent'
                              : 'border-border text-text-muted hover:border-text-muted'
                          }`}
                        >
                          {m.label}
                        </button>
                      ))}
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

                    {/* Mode config panel for structured modes */}
                    {['survey', 'quiz', 'negotiation', 'interview'].includes(form.conversation_mode) && (
                      <div className="mt-3 p-3 rounded-lg border border-border bg-bg-primary/50 space-y-3">
                        <span className="text-xs font-medium text-text-secondary">
                          Configuracion de {
                            { survey: 'Encuesta', quiz: 'Quiz', negotiation: 'Negociacion', interview: 'Entrevista' }[form.conversation_mode]
                          }
                        </span>

                        {/* Questions editor (survey, quiz, interview) */}
                        {['survey', 'quiz', 'interview'].includes(form.conversation_mode) && (
                          <div className="space-y-2">
                            <label className="block text-[11px] text-text-muted">
                              Preguntas (JSON)
                            </label>
                            <textarea
                              value={JSON.stringify(form.mode_config?.questions || [], null, 2)}
                              onChange={e => {
                                try {
                                  const questions = JSON.parse(e.target.value)
                                  setForm(f => ({ ...f, mode_config: { ...f.mode_config, questions } }))
                                } catch { /* invalid JSON, ignore */ }
                              }}
                              rows={8}
                              className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:border-accent/50 transition-colors"
                              placeholder={form.conversation_mode === 'quiz'
                                ? '[{"id":"q1","text":"¿Pregunta?","correct_answer":"Respuesta","points":10,"options":["A","B","C"]}]'
                                : '[{"id":"q1","text":"¿Pregunta?","type":"text"}]'
                              }
                            />
                          </div>
                        )}

                        {/* Quiz-specific: passing score */}
                        {form.conversation_mode === 'quiz' && (
                          <div>
                            <label className="block text-[11px] text-text-muted mb-1">Puntaje minimo para aprobar (%)</label>
                            <input
                              type="number"
                              min={0} max={100}
                              value={form.mode_config?.passing_score ?? 70}
                              onChange={e => setForm(f => ({ ...f, mode_config: { ...f.mode_config, passing_score: Number(e.target.value) } }))}
                              className="w-24 bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/50"
                            />
                          </div>
                        )}

                        {/* Interview-specific: required score */}
                        {form.conversation_mode === 'interview' && (
                          <div>
                            <label className="block text-[11px] text-text-muted mb-1">Puntaje minimo requerido (%)</label>
                            <input
                              type="number"
                              min={0} max={100}
                              value={form.mode_config?.required_score ?? 60}
                              onChange={e => setForm(f => ({ ...f, mode_config: { ...f.mode_config, required_score: Number(e.target.value) } }))}
                              className="w-24 bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/50"
                            />
                          </div>
                        )}

                        {/* Negotiation config */}
                        {form.conversation_mode === 'negotiation' && (
                          <div className="space-y-2">
                            <label className="block text-[11px] text-text-muted">
                              Catalogo de productos (JSON)
                            </label>
                            <textarea
                              value={JSON.stringify(form.mode_config?.product_catalog || [], null, 2)}
                              onChange={e => {
                                try {
                                  const product_catalog = JSON.parse(e.target.value)
                                  setForm(f => ({ ...f, mode_config: { ...f.mode_config, product_catalog } }))
                                } catch { /* invalid JSON */ }
                              }}
                              rows={6}
                              className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:border-accent/50 transition-colors"
                              placeholder='[{"name":"Plan Pro","base_price":500,"min_price":400,"max_discount_pct":20}]'
                            />
                            <div className="flex gap-3">
                              <div className="flex-1">
                                <label className="block text-[11px] text-text-muted mb-1">Nivel de autoridad</label>
                                <select
                                  value={form.mode_config?.authority_level || 'agent'}
                                  onChange={e => setForm(f => ({ ...f, mode_config: { ...f.mode_config, authority_level: e.target.value } }))}
                                  className="w-full bg-bg-secondary border border-border rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-accent/50"
                                >
                                  <option value="agent">Agente</option>
                                  <option value="manager">Manager</option>
                                  <option value="director">Director</option>
                                </select>
                              </div>
                              <div className="flex-1">
                                <label className="block text-[11px] text-text-muted mb-1">Umbral escalacion (%)</label>
                                <input
                                  type="number"
                                  min={0} max={100}
                                  value={form.mode_config?.escalation_threshold_pct ?? 25}
                                  onChange={e => setForm(f => ({ ...f, mode_config: { ...f.mode_config, escalation_threshold_pct: Number(e.target.value) } }))}
                                  className="w-full bg-bg-secondary border border-border rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-accent/50"
                                />
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Survey: thank you message */}
                        {form.conversation_mode === 'survey' && (
                          <div>
                            <label className="block text-[11px] text-text-muted mb-1">Mensaje de agradecimiento</label>
                            <input
                              type="text"
                              value={form.mode_config?.thank_you_message || ''}
                              onChange={e => setForm(f => ({ ...f, mode_config: { ...f.mode_config, thank_you_message: e.target.value } }))}
                              placeholder="Gracias por tus respuestas."
                              className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/50"
                            />
                          </div>
                        )}
                      </div>
                    )}

                    <p className="text-[10px] text-text-muted mt-2">
                      {{ prompt: 'El agente usa el system prompt para improvisar la conversacion.',
                         flow: 'El agente sigue un flujo predefinido con pasos y condiciones.',
                         survey: 'El agente hace preguntas secuenciales y registra respuestas.',
                         quiz: 'El agente evalua conocimiento con puntuacion y respuestas correctas.',
                         negotiation: 'El agente negocia precios con guardrails y catalogo de productos.',
                         interview: 'El agente conduce una entrevista estructurada con evaluacion.',
                      }[form.conversation_mode]}
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

                  {/* Mode toggle: Pipeline vs Realtime vs Gemini Live */}
                  <div className="flex gap-2">
                    {[
                      { value: 'pipeline', label: 'Pipeline', icon: Mic, desc: 'STT + LLM + TTS separados' },
                      { value: 'realtime', label: 'OpenAI Realtime', icon: Zap, desc: 'Multimodal end-to-end' },
                      { value: 'gemini_live', label: 'Gemini Live', icon: Zap, desc: 'Audio nativo, baja latencia' },
                    ].map(mode => {
                      const Icon = mode.icon
                      const isActive = form.agent_mode === mode.value
                      return (
                        <button
                          key={mode.value}
                          type="button"
                          onClick={() => setForm(f => ({ ...f, agent_mode: mode.value }))}
                          className={`flex-1 px-3 py-3 rounded-lg border text-sm font-medium transition-all cursor-pointer ${
                            isActive
                              ? mode.value === 'gemini_live'
                                ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                                : 'border-accent bg-accent/10 text-accent'
                              : 'border-border bg-bg-primary text-text-muted hover:bg-bg-hover'
                          }`}
                        >
                          <div className="flex items-center justify-center gap-2">
                            <Icon size={16} />
                            <span>{mode.label}</span>
                          </div>
                          <p className="text-[11px] mt-1 font-normal opacity-70">{mode.desc}</p>
                        </button>
                      )
                    })}
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
                          onChange={v => {
                            setForm(f => ({ ...f, stt_provider: v, stt_api_key: '' }))
                            setServerKeys(s => ({ ...s, has_stt_api_key: false }))
                          }}
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
                          onChange={v => {
                            setForm(f => ({ ...f, llm_provider: v, llm_api_key: '' }))
                            setServerKeys(s => ({ ...s, has_llm_api_key: false }))
                          }}
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
                          onChange={v => {
                            setForm(f => ({ ...f, tts_provider: v, tts_api_key: '' }))
                            setServerKeys(s => ({ ...s, has_tts_api_key: false }))
                          }}
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

                      {/* Voice Cloning */}
                      {form.tts_provider === 'cartesia' && (
                        <div className="p-4 rounded-lg border border-border bg-bg-primary/50">
                          <VoiceCloning
                            clientId={clientId}
                            agentId={selectedAgent?.id}
                            currentVoiceId={form.voice_id}
                            onVoiceAssigned={(voiceId) => setForm(f => ({ ...f, voice_id: voiceId }))}
                            onClonedVoicesChange={setClonedVoices}
                          />
                        </div>
                      )}
                    </div>
                  ) : isGeminiLive ? (
                    /* Gemini Live config */
                    <div className="space-y-4 p-4 rounded-lg border border-blue-500/30 bg-blue-500/5">
                      <div className="flex items-center gap-2 mb-1">
                        <Zap size={16} className="text-blue-400" />
                        <span className="text-sm font-medium">Configuracion Gemini Live</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-medium">Incluido</span>
                      </div>
                      <p className="text-xs text-text-muted">
                        Audio nativo de Google. No requiere API key adicional — usa la key de la plataforma.
                      </p>
                      <PipelineSelect
                        label="Modelo"
                        value={form.gemini_live_model}
                        onChange={v => setForm(f => ({ ...f, gemini_live_model: v }))}
                        options={GEMINI_LIVE_MODELS}
                      />
                      <PipelineSelect
                        label="Voz"
                        value={form.gemini_live_voice}
                        onChange={v => setForm(f => ({ ...f, gemini_live_voice: v }))}
                        options={GEMINI_LIVE_VOICES.map(v => ({
                          value: v.value,
                          label: `${v.label} — ${v.desc}`,
                        }))}
                      />
                      <PipelineSelect
                        label="Nivel de razonamiento"
                        value={form.gemini_live_thinking_level}
                        onChange={v => setForm(f => ({ ...f, gemini_live_thinking_level: v }))}
                        options={GEMINI_LIVE_THINKING}
                      />
                      <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                        <p className="text-xs text-blue-300">
                          <strong>Tip:</strong> Usa "Minimal" para FAQ bots y respuestas rapidas.
                          Sube a "Medium" o "High" para asistentes que necesitan razonar (ej: Personal Assistant).
                        </p>
                      </div>
                    </div>
                  ) : (
                    /* OpenAI Realtime config */
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

                {/* Voice Rules configurables */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Volume2 size={16} className="text-green-400" />
                    Reglas de Voz
                  </h2>
                  <p className="text-xs text-gray-500">
                    Personaliza cómo responde el agente por voz. Estas reglas se aplican automáticamente a todas las llamadas.
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Máx. oraciones por respuesta</label>
                      <select
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.voice_rules?.max_sentences ?? 2}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), max_sentences: parseInt(e.target.value) },
                          },
                        }))}
                      >
                        <option value={1}>1 (muy corto)</option>
                        <option value={2}>2 (recomendado)</option>
                        <option value={3}>3 (detallado)</option>
                        <option value={4}>4 (extenso)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Formalidad</label>
                      <select
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.voice_rules?.formality ?? 'casual'}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), formality: e.target.value },
                          },
                        }))}
                      >
                        <option value="casual">Casual (tuteo, muletillas)</option>
                        <option value="neutral">Neutral</option>
                        <option value="formal">Formal (usted, profesional)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Estilo regional</label>
                      <select
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.voice_rules?.country_style ?? 'mx'}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), country_style: e.target.value },
                          },
                        }))}
                      >
                        <option value="mx">Mexico</option>
                        <option value="co">Colombia</option>
                        <option value="es">Espana</option>
                        <option value="neutral">Neutral (sin regionalismos)</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.voice_rules?.end_with_question ?? true}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), end_with_question: e.target.checked },
                          },
                        }))}
                      />
                      Terminar con pregunta
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.voice_rules?.confirm_data ?? true}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), confirm_data: e.target.checked },
                          },
                        }))}
                      />
                      Confirmar datos repitiendo
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input
                        type="checkbox"
                        className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.voice_rules?.deny_ai_identity ?? true}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            voice_rules: { ...(f.voice_config?.voice_rules || {}), deny_ai_identity: e.target.checked },
                          },
                        }))}
                      />
                      Negar ser IA
                    </label>
                  </div>
                </Card>
              </div>
            )}

            {/* ── Llamadas Tab ── */}
            {activeTab === 'calls' && (
              <div className="space-y-6">
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

                <div className="border-t border-border pt-4">
                  <BusinessHoursEditor
                    value={form.business_hours}
                    onChange={bh => setForm(f => ({ ...f, business_hours: bh }))}
                  />
                </div>

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

              {/* ── BYOT: Bring Your Own Twilio ── */}
              <ByotTwilioSection clientId={clientId} client={client} setClient={setClient} />
              </div>
            )}

            {/* ── WhatsApp Tab ── */}
            {activeTab === 'whatsapp' && clientId && selectedAgent && (
              <div className="space-y-6">
                <WhatsAppConfig clientId={clientId} agentId={selectedAgent.id} />
                {/* Text Rules para WhatsApp */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <MessageCircle size={16} className="text-green-400" />
                    Formato de Respuestas (WhatsApp)
                  </h2>
                  <p className="text-xs text-gray-500">
                    Controla cómo se formatean las respuestas del agente en WhatsApp.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Longitud maxima (caracteres)</label>
                      <input
                        type="number"
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.text_rules?.whatsapp?.max_length ?? form.voice_config?.text_rules?.max_length ?? 600}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            text_rules: {
                              ...(f.voice_config?.text_rules || {}),
                              whatsapp: { ...(f.voice_config?.text_rules?.whatsapp || {}), max_length: parseInt(e.target.value) || 600 },
                            },
                          },
                        }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Tono</label>
                      <select
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.text_rules?.whatsapp?.tone ?? form.voice_config?.text_rules?.tone ?? 'friendly'}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            text_rules: {
                              ...(f.voice_config?.text_rules || {}),
                              whatsapp: { ...(f.voice_config?.text_rules?.whatsapp || {}), tone: e.target.value },
                            },
                          },
                        }))}
                      >
                        <option value="friendly">Amigable</option>
                        <option value="professional">Profesional</option>
                        <option value="neutral">Neutral</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.text_rules?.whatsapp?.allow_emojis ?? form.voice_config?.text_rules?.allow_emojis ?? true}
                        onChange={e => setForm(f => ({
                          ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), whatsapp: { ...(f.voice_config?.text_rules?.whatsapp || {}), allow_emojis: e.target.checked } } },
                        }))}
                      />
                      Permitir emojis
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.text_rules?.whatsapp?.allow_links ?? form.voice_config?.text_rules?.allow_links ?? true}
                        onChange={e => setForm(f => ({
                          ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), whatsapp: { ...(f.voice_config?.text_rules?.whatsapp || {}), allow_links: e.target.checked } } },
                        }))}
                      />
                      Permitir links
                    </label>
                  </div>
                </Card>
              </div>
            )}

            {/* ── GoHighLevel Tab ── */}
            {activeTab === 'ghl' && clientId && selectedAgent && (
              <div className="space-y-6">
                <GHLConfig clientId={clientId} agentId={selectedAgent.id} />
                {/* Text Rules para GHL */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Zap size={16} className="text-purple-400" />
                    Formato de Respuestas (GoHighLevel)
                  </h2>
                  <p className="text-xs text-gray-500">
                    Controla cómo se formatean las respuestas del agente en los canales de GoHighLevel.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Longitud maxima (caracteres)</label>
                      <input
                        type="number"
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.text_rules?.ghl?.max_length ?? form.voice_config?.text_rules?.max_length ?? 600}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            text_rules: {
                              ...(f.voice_config?.text_rules || {}),
                              ghl: { ...(f.voice_config?.text_rules?.ghl || {}), max_length: parseInt(e.target.value) || 600 },
                            },
                          },
                        }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Tono</label>
                      <select
                        className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                        value={form.voice_config?.text_rules?.ghl?.tone ?? form.voice_config?.text_rules?.tone ?? 'friendly'}
                        onChange={e => setForm(f => ({
                          ...f,
                          voice_config: {
                            ...(f.voice_config || {}),
                            text_rules: {
                              ...(f.voice_config?.text_rules || {}),
                              ghl: { ...(f.voice_config?.text_rules?.ghl || {}), tone: e.target.value },
                            },
                          },
                        }))}
                      >
                        <option value="friendly">Amigable</option>
                        <option value="professional">Profesional</option>
                        <option value="neutral">Neutral</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.text_rules?.ghl?.allow_emojis ?? true}
                        onChange={e => setForm(f => ({
                          ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), ghl: { ...(f.voice_config?.text_rules?.ghl || {}), allow_emojis: e.target.checked } } },
                        }))}
                      />
                      Permitir emojis
                    </label>
                    <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                        checked={form.voice_config?.text_rules?.ghl?.allow_links ?? true}
                        onChange={e => setForm(f => ({
                          ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), ghl: { ...(f.voice_config?.text_rules?.ghl || {}), allow_links: e.target.checked } } },
                        }))}
                      />
                      Permitir links
                    </label>
                  </div>
                </Card>
              </div>
            )}

            {/* ── Inteligencia Tab ── */}
            {activeTab === 'intelligence' && (
              <IntelligenceTab form={form} setForm={setForm} />
            )}

            {/* ── API Tab ── */}
            {activeTab === 'api' && (
              <div className="space-y-6">
                <ApiKeysPanel clientId={clientId} />
                <WebhooksPanel clientId={clientId} />
              </div>
            )}

            {/* ── Widget Tab ── */}
            {activeTab === 'widget' && selectedAgent && (
              <div className="space-y-6">
                {/* Canales del widget */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Globe size={16} className="text-cyan-400" />
                    Canales del Widget
                  </h2>
                  <p className="text-xs text-text-muted">
                    Selecciona que canales habilitar en el widget embeddable de este agente.
                  </p>
                  <div className="flex gap-4">
                    {[
                      { value: 'chat', label: 'Chat de texto', desc: 'Los visitantes escriben mensajes' },
                      { value: 'voice', label: 'Llamada de voz', desc: 'Los visitantes hablan por microfono' },
                    ].map(ch => {
                      const channels = selectedAgent?.widget_channels || ['voice']
                      const active = channels.includes(ch.value)
                      return (
                        <label key={ch.value} className={`flex-1 flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${active ? 'border-accent/40 bg-accent/5' : 'border-border hover:border-border/80'}`}>
                          <input
                            type="checkbox"
                            checked={active}
                            onChange={async (e) => {
                              let next = [...channels]
                              if (e.target.checked) { if (!next.includes(ch.value)) next.push(ch.value) }
                              else { next = next.filter(c => c !== ch.value) }
                              if (next.length === 0) next = ['voice']
                              try {
                                const updated = await api.patch(`/clients/${clientId}/agents/${selectedAgent.id}`, { widget_channels: next })
                                setSelectedAgent(prev => ({ ...prev, widget_channels: next }))
                                setAgents(prev => prev.map(a => a.id === selectedAgent.id ? { ...a, widget_channels: next } : a))
                                toast.success('Canales actualizados')
                              } catch (err) { toast.error(err.message) }
                            }}
                            className="accent-accent mt-0.5"
                          />
                          <div>
                            <span className="text-sm font-medium">{ch.label}</span>
                            <p className="text-[11px] text-text-muted">{ch.desc}</p>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </Card>

                {/* Widget unificado — un solo script para voz + chat */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Globe size={16} className="text-cyan-400" />
                    Widget Embebible
                  </h2>
                  <p className="text-xs text-text-muted">
                    Un solo script que incluye {(selectedAgent?.widget_channels || ['voice']).includes('voice') && (selectedAgent?.widget_channels || ['voice']).includes('chat')
                      ? 'voz y chat de texto. Los visitantes eligen como comunicarse.'
                      : (selectedAgent?.widget_channels || ['voice']).includes('chat')
                        ? 'chat de texto. Los visitantes escriben mensajes.'
                        : 'llamada de voz. Los visitantes hablan por microfono.'
                    }
                  </p>

                  <div className="space-y-3">
                    <label className="text-xs font-medium text-text-secondary">Codigo de instalacion</label>
                    {(() => {
                      const PROD_API = 'https://voiceai-production-f4e4.up.railway.app/api'
                      const envApi = import.meta.env.VITE_API_URL
                      const apiUrl = (envApi && envApi.startsWith('http')) ? envApi : PROD_API
                      const baseUrl = apiUrl.replace(/\/api$/, '')
                      const slug = selectedAgent?.slug || 'tu-agente'
                      return (
                    <div className="relative">
                      <pre className="bg-bg-primary border border-border rounded-lg p-4 text-xs text-green-400 overflow-x-auto whitespace-pre-wrap break-all">
{`<script src="${baseUrl}/widget.js"
  data-agent="${slug}"
  data-api="${apiUrl}">
</script>`}
                      </pre>
                      <button
                        type="button"
                        onClick={() => {
                          const code = `<script src="${baseUrl}/widget.js"\n  data-agent="${slug}"\n  data-api="${apiUrl}">\n</script>`
                          navigator.clipboard.writeText(code)
                          toast.success('Codigo copiado al portapapeles')
                        }}
                        className="absolute top-2 right-2 p-1.5 rounded bg-bg-hover hover:bg-border transition-colors"
                        title="Copiar"
                      >
                        <Check size={14} className="text-text-muted" />
                      </button>
                    </div>
                      )
                    })()}
                  </div>

                  <div className="border border-border rounded-lg p-4 space-y-3">
                    <h3 className="text-xs font-semibold text-text-secondary">Opciones de personalizacion</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      <div className="space-y-1">
                        <span className="text-text-muted">Posicion</span>
                        <code className="block text-cyan-400 bg-bg-primary px-2 py-1 rounded">data-position="bottom-right"</code>
                        <span className="text-text-muted/60">bottom-right o bottom-left</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-text-muted">Color</span>
                        <code className="block text-cyan-400 bg-bg-primary px-2 py-1 rounded">data-color="#00f0ff"</code>
                        <span className="text-text-muted/60">Color hexadecimal del boton</span>
                      </div>
                      <div className="space-y-1">
                        <span className="text-text-muted">Titulo</span>
                        <code className="block text-cyan-400 bg-bg-primary px-2 py-1 rounded">data-title="Hablar con asistente"</code>
                        <span className="text-text-muted/60">Tooltip al pasar el mouse</span>
                      </div>
                    </div>
                  </div>

                  <div className="border border-border rounded-lg p-4 space-y-2">
                    <h3 className="text-xs font-semibold text-text-secondary">Instrucciones</h3>
                    <ol className="text-xs text-text-muted space-y-1.5 list-decimal list-inside">
                      <li>Copia el codigo de arriba</li>
                      <li>Pegalo antes del cierre <code className="text-cyan-400">&lt;/body&gt;</code> en tu pagina HTML</li>
                      <li>El boton aparecera automaticamente en la esquina de tu sitio</li>
                      {(selectedAgent?.widget_channels || ['voice']).length > 1 && (
                        <li>Los visitantes eligen entre voz o texto al hacer clic</li>
                      )}
                      {(selectedAgent?.widget_channels || ['voice']).includes('voice') && (
                        <li>Si el microfono no esta disponible, se ofrece chat de texto como alternativa</li>
                      )}
                    </ol>
                  </div>

                  {(selectedAgent?.widget_channels || ['voice']).includes('voice') && (
                    <div className="border border-yellow-500/20 bg-yellow-500/5 rounded-lg p-3">
                      <p className="text-xs text-yellow-400/80">
                        <strong>Nota:</strong> La llamada de voz requiere acceso al microfono y HTTPS en produccion. Si el microfono no esta disponible{(selectedAgent?.widget_channels || ['voice']).includes('chat') ? ', el widget ofrece chat de texto automaticamente' : ''}.
                      </p>
                    </div>
                  )}
                </Card>

                {/* Preview del widget */}
                <Card className="space-y-4">
                  <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                    <Eye size={16} className="text-green-400" />
                    Previsualizar Widget
                  </h2>
                  <p className="text-xs text-text-muted">
                    Prueba el widget en vivo. El boton aparecera en la esquina inferior derecha de esta pagina.
                  </p>

                  {!window.__voiceAIWidget ? (
                    <Button
                      onClick={() => {
                        const apiUrl = import.meta.env.VITE_API_URL || '/api'
                        const apiBase = apiUrl.replace(/\/api$/, '')
                        const s = document.createElement('script')
                        s.src = apiBase + '/widget.js?v=' + Date.now()
                        s.setAttribute('data-agent', selectedAgent?.slug || '')
                        s.setAttribute('data-api', apiUrl)
                        s.setAttribute('data-color', '#00f0ff')
                        s.setAttribute('data-title', `Hablar con ${selectedAgent?.name || 'agente'}`)
                        s.id = 'vai-preview-script'
                        document.body.appendChild(s)
                        setTimeout(() => setForm(f => ({ ...f, _widgetPreview: true })), 500)
                      }}
                      className="gap-2"
                    >
                      <Mic size={16} />
                      Activar Preview del Widget
                    </Button>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-xs text-green-400">
                        <Check size={14} />
                        <span>Widget activo — busca el boton en la esquina inferior derecha</span>
                      </div>
                      <p className="text-xs text-text-muted">
                        Haz clic en el boton circular para probar el widget.
                      </p>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          const script = document.getElementById('vai-preview-script')
                          if (script) script.remove()
                          document.querySelectorAll('.vai-fab, .vai-tooltip, .vai-status, .vai-mode-menu, .vai-chat-panel, #vai-audio').forEach(el => el.remove())
                          document.querySelectorAll('style').forEach(s => {
                            if (s.textContent?.includes('vai-fab')) s.remove()
                          })
                          window.__voiceAIWidget = false
                          setForm(f => ({ ...f, _widgetPreview: false }))
                        }}
                      >
                        Cerrar Preview
                      </Button>
                    </div>
                  )}
                </Card>

                {/* Text Rules para Widget Chat */}
                {(selectedAgent?.widget_channels || ['voice']).includes('chat') && (
                  <Card className="space-y-4">
                    <h2 className="text-sm font-semibold text-text-secondary flex items-center gap-2">
                      <Globe size={16} className="text-cyan-400" />
                      Formato de Respuestas (Widget Chat)
                    </h2>
                    <p className="text-xs text-gray-500">
                      Controla cómo se formatean las respuestas del agente en el chat del widget.
                    </p>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Longitud maxima (caracteres)</label>
                        <input
                          type="number"
                          className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                          value={form.voice_config?.text_rules?.widget?.max_length ?? form.voice_config?.text_rules?.max_length ?? 800}
                          onChange={e => setForm(f => ({
                            ...f,
                            voice_config: {
                              ...(f.voice_config || {}),
                              text_rules: {
                                ...(f.voice_config?.text_rules || {}),
                                widget: { ...(f.voice_config?.text_rules?.widget || {}), max_length: parseInt(e.target.value) || 800 },
                              },
                            },
                          }))}
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">Tono</label>
                        <select
                          className="w-full bg-[#0a0a0f] border border-gray-700 rounded px-3 py-2 text-sm text-white"
                          value={form.voice_config?.text_rules?.widget?.tone ?? form.voice_config?.text_rules?.tone ?? 'professional'}
                          onChange={e => setForm(f => ({
                            ...f,
                            voice_config: {
                              ...(f.voice_config || {}),
                              text_rules: {
                                ...(f.voice_config?.text_rules || {}),
                                widget: { ...(f.voice_config?.text_rules?.widget || {}), tone: e.target.value },
                              },
                            },
                          }))}
                        >
                          <option value="friendly">Amigable</option>
                          <option value="professional">Profesional</option>
                          <option value="neutral">Neutral</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-4">
                      <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                        <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                          checked={form.voice_config?.text_rules?.widget?.allow_emojis ?? false}
                          onChange={e => setForm(f => ({
                            ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), widget: { ...(f.voice_config?.text_rules?.widget || {}), allow_emojis: e.target.checked } } },
                          }))}
                        />
                        Permitir emojis
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                        <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                          checked={form.voice_config?.text_rules?.widget?.allow_markdown ?? true}
                          onChange={e => setForm(f => ({
                            ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), widget: { ...(f.voice_config?.text_rules?.widget || {}), allow_markdown: e.target.checked } } },
                          }))}
                        />
                        Permitir markdown (negritas, listas)
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                        <input type="checkbox" className="rounded bg-[#0a0a0f] border-gray-700"
                          checked={form.voice_config?.text_rules?.widget?.allow_links ?? true}
                          onChange={e => setForm(f => ({
                            ...f, voice_config: { ...(f.voice_config || {}), text_rules: { ...(f.voice_config?.text_rules || {}), widget: { ...(f.voice_config?.text_rules?.widget || {}), allow_links: e.target.checked } } },
                          }))}
                        />
                        Permitir links
                      </label>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* ── Hooks (Reglas) Tab ── */}
            {activeTab === 'hooks' && selectedAgent && (
              <HooksEditor
                clientId={clientId}
                agentId={selectedAgent.id}
              />
            )}

            {/* ── Insights Tab ── */}
            {activeTab === 'insights' && selectedAgent && (
              <InsightsPanel
                clientId={clientId}
                agentId={selectedAgent.id}
              />
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

            {/* ── PA: Números autorizados ── */}
            {activeTab === 'pa_callers' && selectedAgent && (
              <PaCallersTab agentId={selectedAgent.id} />
            )}

            {/* ── PA: Memoria ── */}
            {activeTab === 'pa_memory' && selectedAgent && (
              <PaMemoryTab agentId={selectedAgent.id} />
            )}

            {/* ── PA: Tareas ── */}
            {activeTab === 'pa_tasks' && selectedAgent && (
              <PaTasksTab agentId={selectedAgent.id} />
            )}

            {/* ── PA: Email ── */}
            {activeTab === 'pa_email' && selectedAgent && (
              <PaEmailTab agentId={selectedAgent.id} />
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
