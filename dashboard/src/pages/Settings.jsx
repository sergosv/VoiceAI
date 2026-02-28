import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, ArrowRight, Volume2, Zap, RefreshCw, Eye, FileText } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader, Spinner } from '../components/ui/Spinner'

const PROVIDER_LABELS = {
  cartesia: 'Cartesia',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI TTS',
}

export function Settings() {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [client, setClient] = useState(null)
  const [voices, setVoices] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  // Cargar client + voces al montar
  useEffect(() => {
    if (user?.role === 'admin') return setLoading(false)
    if (!user?.client_id) return setLoading(false)
    Promise.all([
      api.get(`/clients/${user.client_id}`),
      api.get('/clients/templates').catch(() => []),
    ])
      .then(([c, tpls]) => {
        setClient(c)
        setTemplates(tpls)
        return loadVoicesForProvider(c)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [user])

  async function loadVoicesForProvider(c) {
    const provider = c.tts_provider || 'cartesia'
    const mode = c.voice_mode || 'pipeline'

    if (mode === 'realtime') {
      setVoices([]) // Realtime usa su propio selector
      return
    }

    setLoadingVoices(true)
    try {
      if (provider === 'elevenlabs' || provider === 'openai') {
        // Cargar voces del provider via API
        const v = await api.get(`/voices/provider/${c.id}`)
        setVoices(v)
      } else {
        // Cartesia: catalogo estatico
        const v = await api.get('/voices')
        setVoices(v)
      }
    } catch (err) {
      // Si falla (ej: no hay API key), cargar catalogo default
      console.error('Error cargando voces del provider:', err)
      try {
        const v = await api.get('/voices')
        setVoices(v)
      } catch { /* ignore */ }
    } finally {
      setLoadingVoices(false)
    }
  }

  async function handleRefreshVoices() {
    if (!client) return
    await loadVoicesForProvider(client)
    toast.success('Voces actualizadas')
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!client) return
    setSaving(true)
    try {
      const payload = {
        agent_name: client.agent_name,
        greeting: client.greeting,
        system_prompt: client.system_prompt,
        conversation_examples: client.conversation_examples || null,
        language: client.language,
        max_call_duration_seconds: client.max_call_duration_seconds,
        transfer_number: client.transfer_number || null,
        after_hours_message: client.after_hours_message || null,
      }
      if (client.voice_mode === 'realtime') {
        payload.realtime_voice = client.realtime_voice
      } else {
        payload.voice_id = client.voice_id
      }
      const updated = await api.patch(`/clients/${client.id}`, payload)
      setClient(updated)
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />

  // Admin: redirigir a la gestion de clientes
  if (user?.role === 'admin') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Configuracion</h1>
        <Card className="space-y-4">
          <p className="text-text-secondary">
            Como administrador, puedes configurar cada cliente desde la seccion de clientes.
          </p>
          <Button onClick={() => navigate('/admin/clients')}>
            <ArrowRight size={16} className="mr-2 inline" /> Ir a Clientes
          </Button>
        </Card>
      </div>
    )
  }

  if (!client) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Configuracion</h1>
        <Card><p className="text-text-muted">No se encontro configuracion de cliente.</p></Card>
      </div>
    )
  }

  const ttsProvider = client.tts_provider || 'cartesia'
  const isRealtime = client.voice_mode === 'realtime'
  const providerLabel = isRealtime ? 'OpenAI Realtime' : PROVIDER_LABELS[ttsProvider] || ttsProvider

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuracion</h1>

      <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Agente de voz</h2>
          <Input
            label="Nombre del agente"
            value={client.agent_name}
            onChange={e => setClient({ ...client, agent_name: e.target.value })}
          />
          <Select
            label="Idioma"
            value={client.language}
            onChange={e => setClient({ ...client, language: e.target.value })}
            options={[
              { value: 'es', label: 'Espanol' },
              { value: 'en', label: 'English' },
              { value: 'es-en', label: 'Bilingue' },
            ]}
          />

          {/* Selector de voz dinamico segun provider */}
          {isRealtime ? (
            <RealtimeVoiceSelector
              value={client.realtime_voice || 'alloy'}
              onChange={v => setClient({ ...client, realtime_voice: v })}
            />
          ) : (
            <ProviderVoiceSelector
              voices={voices}
              loading={loadingVoices}
              provider={ttsProvider}
              language={client.language}
              value={client.voice_id}
              onChange={voiceId => setClient({ ...client, voice_id: voiceId })}
              onRefresh={handleRefreshVoices}
            />
          )}

          <Input
            label="Duracion maxima (segundos)"
            type="number"
            value={client.max_call_duration_seconds}
            onChange={e => setClient({ ...client, max_call_duration_seconds: parseInt(e.target.value) || 300 })}
          />
          <Input
            label="Numero de transferencia"
            value={client.transfer_number || ''}
            onChange={e => setClient({ ...client, transfer_number: e.target.value })}
            placeholder="+52..."
          />
        </Card>

        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Mensajes</h2>

          {/* Selector de plantilla de industria */}
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
                      `/clients/templates/${e.target.value}?agent_name=${encodeURIComponent(client.agent_name)}&business_name=${encodeURIComponent(client.name)}`
                    )
                    setClient({ ...client, system_prompt: tpl.content })
                    toast.success('Plantilla aplicada. Puedes editarla.')
                  } catch (err) {
                    toast.error(err.message)
                  }
                }}
                className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
              >
                <option value="">Seleccionar plantilla...</option>
                {templates.map(t => (
                  <option key={t.key} value={t.key}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          <Textarea
            label="Saludo"
            value={client.greeting}
            onChange={e => setClient({ ...client, greeting: e.target.value })}
            rows={3}
          />
          <Textarea
            label="System prompt"
            value={client.system_prompt}
            onChange={e => setClient({ ...client, system_prompt: e.target.value })}
            rows={8}
          />
          <Textarea
            label="Ejemplos de conversacion (few-shot)"
            value={client.conversation_examples || ''}
            onChange={e => setClient({ ...client, conversation_examples: e.target.value })}
            rows={4}
            placeholder="Paciente: ¿Cuánto cuesta una limpieza?&#10;Agente: Mire, la limpieza dental tiene un costo de $800..."
          />
          <Textarea
            label="Mensaje fuera de horario"
            value={client.after_hours_message || ''}
            onChange={e => setClient({ ...client, after_hours_message: e.target.value })}
            rows={2}
          />
          <Button variant="secondary" type="button" onClick={() => setShowPreview(true)}>
            <Eye size={14} className="mr-1 inline" /> Vista previa del prompt
          </Button>
        </Card>

        <div className="lg:col-span-2 flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            <Save size={16} className="mr-2 inline" />
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </Button>
          <span className="text-xs text-text-muted">
            Voz: {providerLabel}
          </span>
        </div>
      </form>

      {/* Modal de vista previa del prompt compilado */}
      {showPreview && (
        <Modal open={true} title="Vista previa del prompt" onClose={() => setShowPreview(false)}>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            <div>
              <h3 className="text-xs font-semibold text-text-muted mb-1">System Prompt</h3>
              <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{client.system_prompt}</pre>
            </div>
            {client.conversation_examples && (
              <div>
                <h3 className="text-xs font-semibold text-text-muted mb-1">Ejemplos de conversacion</h3>
                <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{client.conversation_examples}</pre>
              </div>
            )}
            <p className="text-[10px] text-text-muted">
              * Las reglas de voz y herramientas se agregan automaticamente al prompt en tiempo de ejecucion.
            </p>
          </div>
        </Modal>
      )}
    </div>
  )
}

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

function RealtimeVoiceSelector({ value, onChange }) {
  return (
    <div>
      <label className="block text-xs text-text-muted mb-1">
        <Zap size={12} className="inline mr-1" />
        Voz OpenAI Realtime
      </label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
      >
        {REALTIME_VOICES.map(v => (
          <option key={v.value} value={v.value}>
            {v.label} — {v.desc}
          </option>
        ))}
      </select>
      <p className="text-xs text-text-muted mt-1">
        Modo OpenAI Realtime activo. Cambia el modo en Integraciones.
      </p>
    </div>
  )
}

function ProviderVoiceSelector({ voices, loading, provider, language, value, onChange, onRefresh }) {
  const filtered = useMemo(() => {
    if (!voices?.length) return []
    // Para ElevenLabs/OpenAI mostrar todas, para Cartesia filtrar por idioma
    if (provider !== 'cartesia') return voices
    if (language === 'es-en') return voices
    return voices.filter(v => v.language === language)
  }, [voices, language, provider])

  const grouped = useMemo(() => {
    const groups = {}
    for (const v of filtered) {
      let key
      if (provider === 'cartesia') {
        const lang = v.language === 'es' ? 'Espanol' : 'English'
        const gender = v.gender === 'female' ? 'Mujeres' : 'Hombres'
        key = language === 'es-en' ? `${lang} — ${gender}` : gender
      } else {
        // ElevenLabs/OpenAI: agrupar por genero
        const g = v.gender || 'unknown'
        key = g === 'female' ? 'Mujeres' : g === 'male' ? 'Hombres' : 'Voces'
      }
      if (!groups[key]) groups[key] = []
      groups[key].push(v)
    }
    return groups
  }, [filtered, language, provider])

  const current = voices?.find(v => v.id === value)
  const providerLabel = PROVIDER_LABELS[provider] || provider

  if (loading) {
    return (
      <div>
        <label className="block text-xs text-text-muted mb-1">
          <Volume2 size={12} className="inline mr-1" />
          Voz del agente ({providerLabel})
        </label>
        <div className="flex items-center gap-2 py-2 text-xs text-text-muted">
          <Spinner size={14} /> Cargando voces de {providerLabel}...
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="block text-xs text-text-muted">
          <Volume2 size={12} className="inline mr-1" />
          Voz del agente ({providerLabel})
        </label>
        {provider !== 'cartesia' && (
          <button
            type="button"
            onClick={onRefresh}
            className="text-xs text-accent hover:text-accent/80 flex items-center gap-1"
            title="Recargar voces"
          >
            <RefreshCw size={12} /> Recargar
          </button>
        )}
      </div>
      {filtered.length === 0 ? (
        <p className="text-xs text-text-muted py-2">
          No se encontraron voces. Verifica tu API key en Integraciones.
        </p>
      ) : (
        <>
          <select
            value={value || ''}
            onChange={e => onChange(e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
          >
            {Object.entries(grouped).map(([group, groupVoices]) => (
              <optgroup key={group} label={group}>
                {groupVoices.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.name} — {v.description}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {current && (
            <p className="text-xs text-text-muted mt-1">
              {current.name} ({current.gender === 'female' ? '♀' : current.gender === 'male' ? '♂' : '⚡'}) — {current.description}
            </p>
          )}
        </>
      )}
    </div>
  )
}
