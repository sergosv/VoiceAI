import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Trash2, UserPlus, Phone, Search, ShoppingCart, Plus, Bot, Zap, ChevronDown, ChevronUp, Gift, Coins } from 'lucide-react'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input, Textarea, Select } from '../../components/ui/Input'
import { Modal } from '../../components/ui/Modal'
import { CallsTable } from '../../components/CallsTable'
import { PageLoader } from '../../components/ui/Spinner'

export function ClientDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const [client, setClient] = useState(null)
  const [agents, setAgents] = useState([])
  const [calls, setCalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Modal: crear usuario
  const [showUserModal, setShowUserModal] = useState(false)
  const [userForm, setUserForm] = useState({ email: '', password: '', display_name: '' })
  const [creatingUser, setCreatingUser] = useState(false)

  // Modal: crear agente
  const [showAgentModal, setShowAgentModal] = useState(false)
  const [agentForm, setAgentForm] = useState({ name: '', agent_type: 'inbound', role_description: '' })
  const [creatingAgent, setCreatingAgent] = useState(false)

  // Modal: asignar teléfono (a nivel de agente)
  const [showPhoneModal, setShowPhoneModal] = useState(false)
  const [phoneAgentId, setPhoneAgentId] = useState(null)
  const [phoneTab, setPhoneTab] = useState('search')
  const [phoneForm, setPhoneForm] = useState({ phone_number: '', skip_livekit: false })
  const [assigningPhone, setAssigningPhone] = useState(false)
  const [searchForm, setSearchForm] = useState({ country: 'MX', area_code: '' })
  const [availableNumbers, setAvailableNumbers] = useState([])
  const [searchingNumbers, setSearchingNumbers] = useState(false)
  const [purchasingNumber, setPurchasingNumber] = useState(null)

  // Modal: regalar créditos
  const [showGiftModal, setShowGiftModal] = useState(false)
  const [giftForm, setGiftForm] = useState({ credits: 100, reason: '' })
  const [giftingCredits, setGiftingCredits] = useState(false)
  const [creditBalance, setCreditBalance] = useState(null)

  // Orchestration state
  const [orchOpen, setOrchOpen] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get(`/clients/${id}`),
      api.get(`/clients/${id}/agents`),
      api.get(`/calls?client_id=${id}&per_page=10`),
    ]).then(([c, ag, cl]) => {
      setClient(c)
      setAgents(ag)
      setCalls(cl)
    }).catch(() => navigate('/admin/clients'))
      .finally(() => setLoading(false))

    // Cargar balance de créditos (no bloquea el loading principal)
    api.get(`/billing/balance?client_id=${id}`).then(setCreditBalance).catch(() => {})
  }, [id])

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        name: client.name,
        business_type: client.business_type,
        owner_email: client.owner_email || null,
        language: client.language,
        is_active: client.is_active,
        monthly_minutes_limit: client.monthly_minutes_limit,
        orchestration_mode: client.orchestration_mode,
        orchestrator_model: client.orchestrator_model,
      }
      if (client.orchestrator_prompt) payload.orchestrator_prompt = client.orchestrator_prompt
      const updated = await api.patch(`/clients/${id}`, payload)
      setClient(updated)
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Eliminar cliente',
      message: `Eliminar ${client.name}? Se borraran todos sus datos, agentes, llamadas y documentos.`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${id}`)
      toast.success('Cliente eliminado')
      navigate('/admin/clients')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleCreateUser(e) {
    e.preventDefault()
    setCreatingUser(true)
    try {
      await api.post('/auth/register-user', {
        email: userForm.email,
        password: userForm.password,
        role: 'client',
        client_id: id,
        display_name: userForm.display_name || null,
      })
      toast.success(`Acceso creado para ${userForm.email}`)
      setShowUserModal(false)
      setUserForm({ email: '', password: '', display_name: '' })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreatingUser(false)
    }
  }

  async function handleCreateAgent(e) {
    e.preventDefault()
    setCreatingAgent(true)
    try {
      const newAgent = await api.post(`/clients/${id}/agents`, {
        name: agentForm.name,
        agent_type: agentForm.agent_type,
        role_description: agentForm.role_description || null,
      })
      setAgents([...agents, newAgent])
      toast.success(`Agente "${newAgent.name}" creado`)
      setShowAgentModal(false)
      setAgentForm({ name: '', agent_type: 'inbound', role_description: '' })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreatingAgent(false)
    }
  }

  async function handleGiftCredits(e) {
    e.preventDefault()
    setGiftingCredits(true)
    try {
      await api.post('/billing/admin/gift-credits', {
        client_id: id,
        credits: giftForm.credits,
        reason: giftForm.reason || 'Créditos de regalo (admin)',
        admin_email: user?.email || 'admin',
      })
      toast.success(`${giftForm.credits} créditos otorgados a ${client.name}`)
      setShowGiftModal(false)
      setGiftForm({ credits: 100, reason: '' })
      // Refrescar balance
      api.get(`/billing/balance?client_id=${id}`).then(setCreditBalance).catch(() => {})
    } catch (err) {
      toast.error(err.message)
    } finally {
      setGiftingCredits(false)
    }
  }

  function openPhoneModal(agentId) {
    setPhoneAgentId(agentId)
    setPhoneTab('search')
    setPhoneForm({ phone_number: '', skip_livekit: false })
    setAvailableNumbers([])
    setShowPhoneModal(true)
  }

  async function handleAssignPhone(e) {
    e.preventDefault()
    setAssigningPhone(true)
    try {
      const updated = await api.post(`/clients/${id}/agents/${phoneAgentId}/assign-phone`, {
        phone_number: phoneForm.phone_number,
        skip_livekit: phoneForm.skip_livekit,
      })
      setAgents(agents.map(a => a.id === phoneAgentId ? updated : a))
      toast.success(`Telefono ${phoneForm.phone_number} asignado`)
      setShowPhoneModal(false)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setAssigningPhone(false)
    }
  }

  async function handleSearchNumbers(e) {
    e.preventDefault()
    setSearchingNumbers(true)
    setAvailableNumbers([])
    try {
      const params = new URLSearchParams({ country: searchForm.country, limit: '10' })
      if (searchForm.area_code) params.set('area_code', searchForm.area_code)
      const numbers = await api.get(`/clients/available-numbers?${params}`)
      setAvailableNumbers(numbers)
      if (numbers.length === 0) toast.info('No se encontraron numeros disponibles')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSearchingNumbers(false)
    }
  }

  async function handlePurchaseNumber(phoneNumber) {
    const ok = await confirm({
      title: 'Comprar numero',
      message: `Comprar ${phoneNumber} y asignarlo al agente? Se creara el SIP trunk automaticamente.`,
      confirmText: 'Comprar y asignar',
      variant: 'warning',
    })
    if (!ok) return
    setPurchasingNumber(phoneNumber)
    try {
      const updated = await api.post(`/clients/${id}/agents/${phoneAgentId}/purchase-phone`, {
        phone_number: phoneNumber,
      })
      setAgents(agents.map(a => a.id === phoneAgentId ? updated : a))
      toast.success(`Numero ${phoneNumber} comprado y asignado`)
      setShowPhoneModal(false)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setPurchasingNumber(null)
    }
  }

  if (loading) return <PageLoader />
  if (!client) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate('/admin/clients')}>
          <ArrowLeft size={16} />
        </Button>
        <h1 className="text-2xl font-bold">{client.name}</h1>
        <span className="text-text-muted font-mono text-sm">({client.slug})</span>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => setShowUserModal(true)}>
          <UserPlus size={16} className="mr-2 inline" /> Crear acceso portal
        </Button>
        <Button variant="secondary" onClick={() => setShowAgentModal(true)}>
          <Plus size={16} className="mr-2 inline" /> Agregar agente
        </Button>
        <Button variant="secondary" onClick={() => setShowGiftModal(true)}>
          <Gift size={16} className="mr-2 inline" /> Regalar creditos
        </Button>
      </div>

      {/* Credit balance card */}
      {creditBalance && (
        <Card className="!p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-accent/15 flex items-center justify-center">
            <Coins size={20} className="text-accent" />
          </div>
          <div>
            <p className="text-xs text-text-muted">Balance de creditos</p>
            <p className="text-2xl font-bold">{Math.floor(creditBalance.balance ?? 0)}</p>
          </div>
          <div className="ml-auto text-right text-xs text-text-muted space-y-0.5">
            <p>Comprados: {Math.floor(creditBalance.total_purchased ?? 0)}</p>
            <p>Usados: {Math.floor(creditBalance.total_consumed ?? 0)}</p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Informacion del negocio</h2>
          <Input label="Nombre" value={client.name} onChange={e => setClient({ ...client, name: e.target.value })} />
          <Select
            label="Tipo de negocio"
            value={client.business_type}
            onChange={e => setClient({ ...client, business_type: e.target.value })}
            options={[
              { value: 'generic', label: 'Genérico' },
              { value: 'dental', label: 'Dental' },
              { value: 'medical', label: 'Médico' },
              { value: 'legal', label: 'Legal' },
              { value: 'restaurant', label: 'Restaurante' },
              { value: 'real_estate', label: 'Bienes raíces' },
              { value: 'ecommerce', label: 'E-commerce' },
              { value: 'education', label: 'Educación' },
              { value: 'fitness', label: 'Fitness' },
              { value: 'salon', label: 'Salón de belleza' },
            ]}
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
          <Input
            label="Email del propietario"
            type="email"
            value={client.owner_email || ''}
            onChange={e => setClient({ ...client, owner_email: e.target.value })}
            placeholder="contacto@negocio.com"
          />
          <Input
            label="Limite minutos/mes"
            type="number"
            value={client.monthly_minutes_limit}
            onChange={e => setClient({ ...client, monthly_minutes_limit: parseInt(e.target.value) || 500 })}
          />
          <Select
            label="Estado"
            value={client.is_active ? 'true' : 'false'}
            onChange={e => setClient({ ...client, is_active: e.target.value === 'true' })}
            options={[
              { value: 'true', label: 'Activo' },
              { value: 'false', label: 'Inactivo' },
            ]}
          />
          <div className="text-xs text-text-muted space-y-1">
            <p>Store: <span className="font-mono text-[10px]">{client.file_search_store_id || 'N/A'}</span></p>
          </div>
        </Card>

        {/* Agents list */}
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">
            <Bot size={14} className="inline mr-1.5 -mt-0.5" />
            Agentes ({agents.length})
          </h2>
          {agents.length === 0 ? (
            <p className="text-sm text-text-muted">Sin agentes configurados.</p>
          ) : (
            <div className="space-y-2">
              {agents.map(agent => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-bg-hover transition-colors cursor-pointer"
                  onClick={() => navigate(`/agents/${agent.id}`)}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">{agent.name}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${agent.is_active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                        {agent.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">{agent.agent_type}</span>
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">
                      {agent.phone_number ? (
                        <span className="font-mono">{agent.phone_number}</span>
                      ) : (
                        <span className="text-yellow-400/70">Sin telefono</span>
                      )}
                      <span className="mx-1.5">·</span>
                      <span>{agent.agent_mode}</span>
                      <span className="mx-1.5">·</span>
                      <span>{(agent.voice_config?.provider || 'cartesia')}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {!agent.phone_number && (
                      <Button
                        variant="secondary"
                        className="!py-1 !px-2 text-xs"
                        onClick={(e) => { e.stopPropagation(); openPhoneModal(agent.id) }}
                      >
                        <Phone size={12} />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Modo Inteligente (Orchestration) */}
      <Card className="space-y-0">
        <button
          type="button"
          onClick={() => setOrchOpen(o => !o)}
          className="w-full flex items-center justify-between cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Zap size={20} className="text-purple-400" />
            <h2 className="text-lg font-semibold">Modo Inteligente</h2>
            {client.orchestration_mode === 'intelligent' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-medium">Activo</span>
            )}
          </div>
          {orchOpen
            ? <ChevronUp size={20} className="text-text-muted" />
            : <ChevronDown size={20} className="text-text-muted" />
          }
        </button>

        {orchOpen && (
          <div className="mt-4 space-y-4">
            <p className="text-xs text-text-muted">
              Permite que todos los agentes esten disponibles en el mismo telefono.
              Un coordinador IA decide en tiempo real cual agente responde segun la intencion del usuario.
            </p>

            {agents.length < 2 ? (
              <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-sm text-yellow-400">
                Necesitas al menos 2 agentes para activar el Modo Inteligente.
              </div>
            ) : (
              <>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={client.orchestration_mode === 'intelligent'}
                    onChange={e => setClient({
                      ...client,
                      orchestration_mode: e.target.checked ? 'intelligent' : 'simple',
                    })}
                    className="accent-purple-400 w-4 h-4"
                  />
                  <span className="text-sm font-medium">
                    Activar orquestacion multi-agente
                  </span>
                </label>

                {client.orchestration_mode === 'intelligent' && (
                  <div className="space-y-3 pl-7">
                    <Select
                      label="Modelo coordinador"
                      value={client.orchestrator_model || 'gemini-2.0-flash'}
                      onChange={e => setClient({ ...client, orchestrator_model: e.target.value })}
                      options={[
                        { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (rapido)' },
                        { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (mejor)' },
                      ]}
                    />

                    <div>
                      <label className="block text-xs text-text-muted mb-1">Agentes en el roster</label>
                      <div className="space-y-1.5">
                        {agents.map(agent => (
                          <div key={agent.id} className="flex items-center gap-3 p-2 rounded-lg bg-bg-secondary border border-border text-sm">
                            <span className="font-medium flex-1 truncate">{agent.name}</span>
                            <span className="text-[10px] text-text-muted truncate max-w-[200px]">
                              {agent.role_description || 'Sin descripcion de rol'}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">
                              P:{agent.orchestrator_priority ?? 0}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="text-[10px] text-text-muted mt-1">
                        Configura el rol y prioridad de cada agente en su pagina de detalle.
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={saving}>
          <Save size={16} className="mr-2 inline" />
          {saving ? 'Guardando...' : 'Guardar'}
        </Button>
        <Button variant="danger" onClick={handleDelete}>
          <Trash2 size={16} className="mr-2 inline" /> Eliminar
        </Button>
      </div>

      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Llamadas recientes</h2>
        <CallsTable calls={calls} />
      </Card>

      {/* Modal: Crear usuario */}
      <Modal open={showUserModal} onClose={() => setShowUserModal(false)} title="Crear acceso al portal">
        <form onSubmit={handleCreateUser} className="space-y-4">
          <Input
            label="Email del usuario"
            type="email"
            value={userForm.email}
            onChange={e => setUserForm(f => ({ ...f, email: e.target.value }))}
            required
          />
          <Input
            label="Contrasena"
            type="password"
            value={userForm.password}
            onChange={e => setUserForm(f => ({ ...f, password: e.target.value }))}
            required
            placeholder="Minimo 6 caracteres"
          />
          <Input
            label="Nombre (opcional)"
            value={userForm.display_name}
            onChange={e => setUserForm(f => ({ ...f, display_name: e.target.value }))}
          />
          <Button type="submit" className="w-full" disabled={creatingUser}>
            {creatingUser ? 'Creando...' : 'Crear acceso'}
          </Button>
        </form>
      </Modal>

      {/* Modal: Crear agente */}
      <Modal open={showAgentModal} onClose={() => setShowAgentModal(false)} title="Agregar agente">
        <form onSubmit={handleCreateAgent} className="space-y-4">
          <Input
            label="Nombre del agente"
            value={agentForm.name}
            onChange={e => setAgentForm(f => ({ ...f, name: e.target.value }))}
            required
            placeholder="Ej: Maria, Soporte, Ventas"
          />
          <Select
            label="Tipo"
            value={agentForm.agent_type}
            onChange={e => setAgentForm(f => ({ ...f, agent_type: e.target.value }))}
            options={[
              { value: 'inbound', label: 'Inbound (recibe llamadas)' },
              { value: 'outbound', label: 'Outbound (hace llamadas)' },
              { value: 'both', label: 'Ambos' },
            ]}
          />
          <Textarea
            label="Rol del agente (para el coordinador IA)"
            value={agentForm.role_description}
            onChange={e => setAgentForm(f => ({ ...f, role_description: e.target.value }))}
            rows={2}
            placeholder="Ej: Agente de ventas que maneja cotizaciones y cierre. Agente de soporte que resuelve problemas tecnicos."
          />
          <p className="text-xs text-text-muted">
            El rol describe que hace este agente para que el coordinador sepa cuando derivar llamadas. Se creara con prompt y configuracion por defecto.
          </p>
          <Button type="submit" className="w-full" disabled={creatingAgent}>
            {creatingAgent ? 'Creando...' : 'Crear agente'}
          </Button>
        </form>
      </Modal>

      {/* Modal: Asignar telefono a agente */}
      <Modal open={showPhoneModal} onClose={() => setShowPhoneModal(false)} title="Asignar telefono al agente" maxWidth="max-w-2xl">
        <div className="flex gap-1 mb-4 border-b border-border">
          <button
            className={`px-4 py-2 text-sm font-medium cursor-pointer ${phoneTab === 'search' ? 'text-accent border-b-2 border-accent' : 'text-text-muted hover:text-text-secondary'}`}
            onClick={() => setPhoneTab('search')}
          >
            <Search size={14} className="inline mr-1.5 -mt-0.5" />Buscar y comprar
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium cursor-pointer ${phoneTab === 'manual' ? 'text-accent border-b-2 border-accent' : 'text-text-muted hover:text-text-secondary'}`}
            onClick={() => setPhoneTab('manual')}
          >
            <Phone size={14} className="inline mr-1.5 -mt-0.5" />Asignar existente
          </button>
        </div>

        {phoneTab === 'search' && (
          <div className="space-y-4">
            <form onSubmit={handleSearchNumbers} className="flex gap-3 items-end">
              <Select
                label="Pais"
                value={searchForm.country}
                onChange={e => setSearchForm(f => ({ ...f, country: e.target.value }))}
                options={[
                  { value: 'MX', label: 'Mexico (+52)' },
                  { value: 'US', label: 'Estados Unidos (+1)' },
                  { value: 'CO', label: 'Colombia (+57)' },
                  { value: 'CL', label: 'Chile (+56)' },
                  { value: 'AR', label: 'Argentina (+54)' },
                ]}
              />
              <Input
                label="Codigo de area"
                value={searchForm.area_code}
                onChange={e => setSearchForm(f => ({ ...f, area_code: e.target.value }))}
                placeholder="999"
              />
              <Button type="submit" disabled={searchingNumbers} className="shrink-0">
                <Search size={14} className="mr-1.5 inline" />
                {searchingNumbers ? 'Buscando...' : 'Buscar'}
              </Button>
            </form>

            {availableNumbers.length > 0 && (
              <div className="border border-border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-bg-tertiary text-text-secondary">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Numero</th>
                      <th className="text-left px-3 py-2 font-medium">Localidad</th>
                      <th className="text-left px-3 py-2 font-medium">Region</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {availableNumbers.map(n => (
                      <tr key={n.phone_number} className="hover:bg-bg-tertiary/50">
                        <td className="px-3 py-2 font-mono">{n.phone_number}</td>
                        <td className="px-3 py-2 text-text-secondary">{n.locality || '—'}</td>
                        <td className="px-3 py-2 text-text-secondary">{n.region || '—'}</td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            variant="secondary"
                            onClick={() => handlePurchaseNumber(n.phone_number)}
                            disabled={purchasingNumber === n.phone_number}
                            className="!py-1 !px-3 text-xs"
                          >
                            <ShoppingCart size={12} className="mr-1 inline" />
                            {purchasingNumber === n.phone_number ? 'Comprando...' : 'Comprar'}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {phoneTab === 'manual' && (
          <form onSubmit={handleAssignPhone} className="space-y-4">
            <Input
              label="Numero de telefono"
              value={phoneForm.phone_number}
              onChange={e => setPhoneForm(f => ({ ...f, phone_number: e.target.value }))}
              required
              placeholder="+529994890531"
            />
            <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={phoneForm.skip_livekit}
                onChange={e => setPhoneForm(f => ({ ...f, skip_livekit: e.target.checked }))}
                className="accent-accent"
              />
              Omitir configuracion SIP en LiveKit
            </label>
            <Button type="submit" className="w-full" disabled={assigningPhone}>
              {assigningPhone ? 'Configurando...' : 'Asignar telefono'}
            </Button>
          </form>
        )}
      </Modal>

      {/* Modal: Regalar créditos */}
      <Modal open={showGiftModal} onClose={() => setShowGiftModal(false)} title="Regalar creditos">
        <form onSubmit={handleGiftCredits} className="space-y-4">
          <div className="p-3 rounded-lg bg-accent/5 border border-accent/20 text-sm">
            <p className="text-text-secondary">
              Cliente: <span className="font-medium text-text-primary">{client.name}</span>
            </p>
            {creditBalance && (
              <p className="text-text-muted mt-1">
                Balance actual: <span className="font-mono font-medium text-accent">{Math.floor(creditBalance.balance ?? 0)}</span> creditos
              </p>
            )}
          </div>
          <Input
            label="Cantidad de creditos"
            type="number"
            min={1}
            max={100000}
            value={giftForm.credits}
            onChange={e => setGiftForm(f => ({ ...f, credits: parseInt(e.target.value) || 0 }))}
            required
          />
          <Input
            label="Motivo (opcional)"
            value={giftForm.reason}
            onChange={e => setGiftForm(f => ({ ...f, reason: e.target.value }))}
            placeholder="Ej: Prueba, compensacion, bienvenida..."
          />
          <Button type="submit" className="w-full" disabled={giftingCredits || giftForm.credits < 1}>
            <Gift size={16} className="mr-2 inline" />
            {giftingCredits ? 'Otorgando...' : `Regalar ${giftForm.credits} creditos`}
          </Button>
        </form>
      </Modal>
    </div>
  )
}
