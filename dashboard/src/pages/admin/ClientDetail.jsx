import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, Trash2, UserPlus, Phone, Search, ShoppingCart } from 'lucide-react'
import { api } from '../../lib/api'
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
  const toast = useToast()
  const confirm = useConfirm()
  const [client, setClient] = useState(null)
  const [calls, setCalls] = useState([])
  const [voices, setVoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Modal: crear usuario
  const [showUserModal, setShowUserModal] = useState(false)
  const [userForm, setUserForm] = useState({ email: '', password: '', display_name: '' })
  const [creatingUser, setCreatingUser] = useState(false)

  // Modal: asignar teléfono
  const [showPhoneModal, setShowPhoneModal] = useState(false)
  const [phoneTab, setPhoneTab] = useState('search') // 'search' | 'manual'
  const [phoneForm, setPhoneForm] = useState({ phone_number: '', skip_livekit: false })
  const [assigningPhone, setAssigningPhone] = useState(false)

  // Buscar y comprar números
  const [searchForm, setSearchForm] = useState({ country: 'MX', area_code: '' })
  const [availableNumbers, setAvailableNumbers] = useState([])
  const [searchingNumbers, setSearchingNumbers] = useState(false)
  const [purchasingNumber, setPurchasingNumber] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get(`/clients/${id}`),
      api.get(`/calls?client_id=${id}&per_page=10`),
      api.get('/voices'),
    ]).then(([c, cl, v]) => {
      setClient(c)
      setCalls(cl)
      setVoices(v)
    }).catch(() => navigate('/admin/clients'))
      .finally(() => setLoading(false))
  }, [id])

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await api.patch(`/clients/${id}`, {
        name: client.name,
        agent_name: client.agent_name,
        greeting: client.greeting,
        system_prompt: client.system_prompt,
        language: client.language,
        voice_id: client.voice_id,
        is_active: client.is_active,
        max_call_duration_seconds: client.max_call_duration_seconds,
        monthly_minutes_limit: client.monthly_minutes_limit,
        transfer_number: client.transfer_number || null,
        after_hours_message: client.after_hours_message || null,
      })
      setClient(updated)
      toast.success('Configuración guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Eliminar cliente',
      message: `¿Eliminar ${client.name}? Se borrarán todos sus datos, llamadas y documentos.`,
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

  async function handleAssignPhone(e) {
    e.preventDefault()
    setAssigningPhone(true)
    try {
      const updated = await api.post(`/clients/${id}/assign-phone`, {
        phone_number: phoneForm.phone_number,
        skip_livekit: phoneForm.skip_livekit,
      })
      setClient(updated)
      toast.success(`Teléfono ${phoneForm.phone_number} asignado`)
      setShowPhoneModal(false)
      setPhoneForm({ phone_number: '', skip_livekit: false })
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
      if (numbers.length === 0) toast.info('No se encontraron números disponibles')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSearchingNumbers(false)
    }
  }

  async function handlePurchaseNumber(phoneNumber) {
    const ok = await confirm({
      title: 'Comprar número',
      message: `¿Comprar ${phoneNumber} y asignarlo a ${client.name}? Se creará el SIP trunk automáticamente. Se aplicarán cargos de Twilio.`,
      confirmText: 'Comprar y asignar',
      variant: 'warning',
    })
    if (!ok) return
    setPurchasingNumber(phoneNumber)
    try {
      const updated = await api.post(`/clients/${id}/purchase-phone`, {
        phone_number: phoneNumber,
      })
      setClient(updated)
      toast.success(`Número ${phoneNumber} comprado y asignado`)
      setShowPhoneModal(false)
      setAvailableNumbers([])
    } catch (err) {
      toast.error(err.message)
    } finally {
      setPurchasingNumber(null)
    }
  }

  if (loading) return <PageLoader />
  if (!client) return null

  // Encontrar voice key actual
  const currentVoice = voices.find(v => v.id === client.voice_id)

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
        <Button variant="secondary" onClick={() => setShowPhoneModal(true)}>
          <Phone size={16} className="mr-2 inline" />
          {client.phone_number ? 'Cambiar teléfono' : 'Asignar teléfono'}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Información</h2>
          <Input label="Nombre" value={client.name} onChange={e => setClient({ ...client, name: e.target.value })} />
          <Input label="Agente" value={client.agent_name} onChange={e => setClient({ ...client, agent_name: e.target.value })} />
          <Select
            label="Voz"
            value={client.voice_id}
            onChange={e => setClient({ ...client, voice_id: e.target.value })}
            options={voices.map(v => ({ value: v.id, label: `${v.name} — ${v.description}` }))}
          />
          <Select
            label="Idioma"
            value={client.language}
            onChange={e => setClient({ ...client, language: e.target.value })}
            options={[
              { value: 'es', label: 'Español' },
              { value: 'en', label: 'English' },
              { value: 'es-en', label: 'Bilingüe' },
            ]}
          />
          <Input
            label="Duración máxima (seg)"
            type="number"
            value={client.max_call_duration_seconds}
            onChange={e => setClient({ ...client, max_call_duration_seconds: parseInt(e.target.value) || 300 })}
          />
          <Input
            label="Límite minutos/mes"
            type="number"
            value={client.monthly_minutes_limit}
            onChange={e => setClient({ ...client, monthly_minutes_limit: parseInt(e.target.value) || 500 })}
          />
          <Input
            label="Número de transferencia"
            value={client.transfer_number || ''}
            onChange={e => setClient({ ...client, transfer_number: e.target.value })}
            placeholder="+52..."
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
            <p>Teléfono: <span className="font-mono">{client.phone_number || 'Sin asignar'}</span></p>
            <p>Store: <span className="font-mono text-[10px]">{client.file_search_store_id || 'N/A'}</span></p>
          </div>
        </Card>

        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Mensajes</h2>
          <Textarea label="Saludo" value={client.greeting} onChange={e => setClient({ ...client, greeting: e.target.value })} rows={3} />
          <Textarea label="System prompt" value={client.system_prompt} onChange={e => setClient({ ...client, system_prompt: e.target.value })} rows={8} />
          <Textarea
            label="Mensaje fuera de horario"
            value={client.after_hours_message || ''}
            onChange={e => setClient({ ...client, after_hours_message: e.target.value })}
            rows={2}
          />
        </Card>
      </div>

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
            label="Contraseña"
            type="password"
            value={userForm.password}
            onChange={e => setUserForm(f => ({ ...f, password: e.target.value }))}
            required
            placeholder="Mínimo 6 caracteres"
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

      {/* Modal: Asignar teléfono (2 tabs) */}
      <Modal open={showPhoneModal} onClose={() => setShowPhoneModal(false)} title="Asignar teléfono" maxWidth="max-w-2xl">
        {/* Tabs */}
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

        {/* Tab: Buscar y comprar */}
        {phoneTab === 'search' && (
          <div className="space-y-4">
            <form onSubmit={handleSearchNumbers} className="flex gap-3 items-end">
              <Select
                label="País"
                value={searchForm.country}
                onChange={e => setSearchForm(f => ({ ...f, country: e.target.value }))}
                options={[
                  { value: 'MX', label: 'México (+52)' },
                  { value: 'US', label: 'Estados Unidos (+1)' },
                  { value: 'CO', label: 'Colombia (+57)' },
                  { value: 'CL', label: 'Chile (+56)' },
                  { value: 'AR', label: 'Argentina (+54)' },
                ]}
              />
              <Input
                label="Código de área"
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
                      <th className="text-left px-3 py-2 font-medium">Número</th>
                      <th className="text-left px-3 py-2 font-medium">Localidad</th>
                      <th className="text-left px-3 py-2 font-medium">Región</th>
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

            <p className="text-xs text-text-muted">
              Busca números disponibles en Twilio. Al comprar se configura automáticamente el SIP trunk en LiveKit.
            </p>
          </div>
        )}

        {/* Tab: Asignar existente */}
        {phoneTab === 'manual' && (
          <form onSubmit={handleAssignPhone} className="space-y-4">
            <Input
              label="Número de teléfono"
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
              Omitir configuración SIP en LiveKit (configurar manualmente)
            </label>
            <p className="text-xs text-text-muted">
              El número debe existir en tu cuenta de Twilio. Se configurará el SIP trunk y dispatch rule automáticamente.
            </p>
            <Button type="submit" className="w-full" disabled={assigningPhone}>
              {assigningPhone ? 'Configurando...' : 'Asignar teléfono'}
            </Button>
          </form>
        )}
      </Modal>
    </div>
  )
}
