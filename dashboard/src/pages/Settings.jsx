import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, ArrowRight, Volume2, Zap, RefreshCw, Eye, FileText, Bot, Plus } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader, Spinner } from '../components/ui/Spinner'
import { PromptAssistant } from '../components/PromptAssistant'
import { ChatTesterButton } from '../components/ChatTester'

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
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [voices, setVoices] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingVoices, setLoadingVoices] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [newAgentForm, setNewAgentForm] = useState({ name: '', agent_type: 'inbound', role_description: '' })
  const [creatingAgent, setCreatingAgent] = useState(false)

  useEffect(() => {
    if (user?.role === 'admin') return setLoading(false)
    if (!user?.client_id) return setLoading(false)
    const clientId = user.client_id
    Promise.all([
      api.get(`/clients/${clientId}`),
      api.get(`/clients/${clientId}/agents`),
      api.get('/clients/templates').catch(() => []),
    ])
      .then(([c, ag, tpls]) => {
        setClient(c)
        setAgents(ag)
        setTemplates(tpls)
        // Auto-select the first (or only) agent
        if (ag.length > 0) {
          setSelectedAgent(ag[0])
          return loadVoicesForAgent(ag[0], clientId)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [user])

  async function loadVoicesForAgent(agent, clientId) {
    const vc = agent?.voice_config || {}
    const provider = vc.provider || 'cartesia'
    const mode = agent?.agent_mode || 'pipeline'

    if (mode === 'realtime') {
      setVoices([])
      return
    }

    setLoadingVoices(true)
    try {
      if (provider === 'elevenlabs' || provider === 'openai') {
        const v = await api.get(`/voices/provider/${clientId}?agent_id=${agent.id}`)
        setVoices(v)
      } else {
        const v = await api.get('/voices')
        setVoices(v)
      }
    } catch (err) {
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
    if (!selectedAgent || !client) return
    await loadVoicesForAgent(selectedAgent, client.id)
    toast.success('Voces actualizadas')
  }

  function handleSelectAgent(agent) {
    setSelectedAgent(agent)
    if (client) loadVoicesForAgent(agent, client.id)
  }

  async function handleCreateAgent(e) {
    e.preventDefault()
    if (!newAgentForm.name || !client) return
    setCreatingAgent(true)
    try {
      const created = await api.post(`/clients/${client.id}/agents`, {
        name: newAgentForm.name,
        agent_type: newAgentForm.agent_type,
        role_description: newAgentForm.role_description || null,
      })
      setAgents(prev => [...prev, created])
      setSelectedAgent(created)
      setShowCreateAgent(false)
      setNewAgentForm({ name: '', agent_type: 'inbound', role_description: '' })
      toast.success(`Agente "${created.name}" creado`)
      await loadVoicesForAgent(created, client.id)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreatingAgent(false)
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!selectedAgent || !client) return
    setSaving(true)
    try {
      const vc = selectedAgent.voice_config || {}
      const payload = {
        name: selectedAgent.name,
        greeting: selectedAgent.greeting,
        system_prompt: selectedAgent.system_prompt,
        examples: selectedAgent.examples || null,
        max_call_duration_seconds: selectedAgent.max_call_duration_seconds,
        transfer_number: selectedAgent.transfer_number || null,
        after_hours_message: selectedAgent.after_hours_message || null,
      }
      if (selectedAgent.agent_mode === 'realtime') {
        payload.realtime_voice = vc.realtime_voice || 'alloy'
      } else {
        payload.voice_id = vc.voice_id
      }
      const updated = await api.patch(`/clients/${client.id}/agents/${selectedAgent.id}`, payload)
      setSelectedAgent(updated)
      setAgents(agents.map(a => a.id === updated.id ? updated : a))
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />

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

  // Si hay multiples agentes, mostrar selector
  const multiAgent = agents.length > 1

  const vc = selectedAgent?.voice_config || {}
  const ttsProvider = vc.provider || 'cartesia'
  const isRealtime = selectedAgent?.agent_mode === 'realtime'
  const providerLabel = isRealtime ? 'OpenAI Realtime' : PROVIDER_LABELS[ttsProvider] || ttsProvider

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuracion</h1>

      {/* Selector de agentes */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-secondary">
            <Bot size={14} className="inline mr-1.5 -mt-0.5" />
            Agentes ({agents.length})
          </h2>
          <Button variant="secondary" onClick={() => setShowCreateAgent(true)} className="text-xs">
            <Plus size={14} className="mr-1 inline" /> Nuevo agente
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {agents.map(agent => (
            <button
              key={agent.id}
              onClick={() => handleSelectAgent(agent)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                selectedAgent?.id === agent.id
                  ? 'bg-accent/20 text-accent border border-accent/50'
                  : 'bg-bg-tertiary text-text-secondary border border-border hover:bg-bg-hover'
              }`}
            >
              {agent.name}
              {agent.phone_number && (
                <span className="ml-1.5 text-xs text-text-muted font-mono">{agent.phone_number}</span>
              )}
            </button>
          ))}
        </div>
        {multiAgent && selectedAgent && (
          <p className="text-xs text-text-muted">
            Para configuracion avanzada (pipeline, API keys) ve a{' '}
            <button onClick={() => navigate(`/agents/${selectedAgent?.id}`)} className="text-accent hover:underline cursor-pointer">
              detalle del agente
            </button>.
          </p>
        )}
      </Card>

      {/* Modo Inteligente toggle */}
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
            Un coordinador IA decide cual responde segun lo que pida el usuario.
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
              <p className="text-[10px] text-text-muted mt-1">
                Configura el rol de cada agente en su{' '}
                <button onClick={() => navigate(`/agents/${selectedAgent?.id}`)} className="text-accent hover:underline cursor-pointer">
                  pagina de detalle
                </button>.
              </p>
            </div>
          )}
        </Card>
      )}

      {selectedAgent && (
        <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="space-y-4">
            <h2 className="text-sm font-semibold text-text-secondary">Agente de voz</h2>
            <Input
              label="Nombre del agente"
              value={selectedAgent.name}
              onChange={e => setSelectedAgent({ ...selectedAgent, name: e.target.value })}
            />

            {isRealtime ? (
              <RealtimeVoiceSelector
                value={vc.realtime_voice || 'alloy'}
                onChange={v => setSelectedAgent({
                  ...selectedAgent,
                  voice_config: { ...vc, realtime_voice: v },
                })}
              />
            ) : (
              <ProviderVoiceSelector
                voices={voices}
                loading={loadingVoices}
                provider={ttsProvider}
                language={client.language}
                value={vc.voice_id}
                onChange={voiceId => setSelectedAgent({
                  ...selectedAgent,
                  voice_config: { ...vc, voice_id: voiceId },
                })}
                onRefresh={handleRefreshVoices}
              />
            )}

            <Input
              label="Duracion maxima (segundos)"
              type="number"
              value={selectedAgent.max_call_duration_seconds}
              onChange={e => setSelectedAgent({ ...selectedAgent, max_call_duration_seconds: parseInt(e.target.value) || 300 })}
            />
            <Input
              label="Numero de transferencia"
              value={selectedAgent.transfer_number || ''}
              onChange={e => setSelectedAgent({ ...selectedAgent, transfer_number: e.target.value })}
              placeholder="+52..."
            />
          </Card>

          <Card className="space-y-4">
            <h2 className="text-sm font-semibold text-text-secondary">Mensajes</h2>

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
                        `/clients/templates/${e.target.value}?agent_name=${encodeURIComponent(selectedAgent.name)}&business_name=${encodeURIComponent(client.name)}`
                      )
                      setSelectedAgent({ ...selectedAgent, system_prompt: tpl.content })
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
              value={selectedAgent.greeting}
              onChange={e => setSelectedAgent({ ...selectedAgent, greeting: e.target.value })}
              rows={3}
            />
            <div className="flex items-center justify-between">
              <label className="block text-xs text-text-muted">System prompt</label>
              <PromptAssistant
                type="agent"
                currentPrompt={selectedAgent.system_prompt}
                onApply={prompt => setSelectedAgent({ ...selectedAgent, system_prompt: prompt })}
                agentName={selectedAgent.name}
                businessName={client.name}
              />
            </div>
            <Textarea
              value={selectedAgent.system_prompt}
              onChange={e => setSelectedAgent({ ...selectedAgent, system_prompt: e.target.value })}
              rows={8}
            />
            <Textarea
              label="Ejemplos de conversacion (few-shot)"
              value={selectedAgent.examples || ''}
              onChange={e => setSelectedAgent({ ...selectedAgent, examples: e.target.value })}
              rows={4}
              placeholder="Paciente: Cuanto cuesta una limpieza?&#10;Agente: Mire, la limpieza dental tiene un costo de $800..."
            />
            <Textarea
              label="Mensaje fuera de horario"
              value={selectedAgent.after_hours_message || ''}
              onChange={e => setSelectedAgent({ ...selectedAgent, after_hours_message: e.target.value })}
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
            {selectedAgent && (
              <ChatTesterButton
                agentId={selectedAgent.id}
                agentName={selectedAgent.name}
                agentType={selectedAgent.agent_type}
              />
            )}
            <span className="text-xs text-text-muted">
              Voz: {providerLabel}
            </span>
            {multiAgent && (
              <Button variant="secondary" type="button" onClick={() => navigate(`/agents/${selectedAgent.id}`)}>
                Configuracion avanzada
              </Button>
            )}
          </div>
        </form>
      )}

      {showPreview && selectedAgent && (
        <Modal open={true} title="Vista previa del prompt" onClose={() => setShowPreview(false)}>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            <div>
              <h3 className="text-xs font-semibold text-text-muted mb-1">System Prompt</h3>
              <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{selectedAgent.system_prompt}</pre>
            </div>
            {selectedAgent.examples && (
              <div>
                <h3 className="text-xs font-semibold text-text-muted mb-1">Ejemplos de conversacion</h3>
                <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap">{selectedAgent.examples}</pre>
              </div>
            )}
            <p className="text-[10px] text-text-muted">
              * Las reglas de voz y herramientas se agregan automaticamente al prompt en tiempo de ejecucion.
            </p>
          </div>
        </Modal>
      )}

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
