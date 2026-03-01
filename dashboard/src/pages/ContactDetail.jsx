import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { PageLoader } from '../components/ui/Spinner'
import { ContactTimeline } from '../components/ContactTimeline'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { ArrowLeft, Save, Phone, Mail, Clock, Trash2, PhoneCall, TrendingUp, Calendar, Brain, Plus, Globe, MessageSquare } from 'lucide-react'

const TABS = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'calls', label: 'Llamadas' },
  { key: 'appointments', label: 'Citas' },
  { key: 'memoria', label: 'Memoria' },
]

const SENTIMIENTO_COLORS = {
  positivo: 'bg-green-500/20 text-green-400',
  neutral: 'bg-yellow-500/20 text-yellow-400',
  negativo: 'bg-red-500/20 text-red-400',
}

const CHANNEL_ICONS = {
  call: { icon: PhoneCall, label: 'Llamada', color: 'text-accent' },
  outbound_call: { icon: PhoneCall, label: 'Outbound', color: 'text-orange-400' },
  whatsapp: { icon: MessageSquare, label: 'WhatsApp', color: 'text-green-400' },
  web_chat: { icon: Globe, label: 'Web Chat', color: 'text-blue-400' },
}

const CHANNEL_FILTERS = [
  { key: null, label: 'Todos' },
  { key: 'call', label: 'Llamadas' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'web_chat', label: 'Web Chat' },
]

const IDENTIFIER_ICONS = {
  phone: Phone,
  email: Mail,
  whatsapp: MessageSquare,
  web_session: Globe,
}

export function ContactDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [contact, setContact] = useState(null)
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('timeline')
  const [form, setForm] = useState({ name: '', email: '', notes: '', tags: '' })

  // Memoria
  const [memories, setMemories] = useState([])
  const [memoriesLoading, setMemoriesLoading] = useState(false)
  const [channelFilter, setChannelFilter] = useState(null)
  const [identifiers, setIdentifiers] = useState([])
  const [showAddIdentifier, setShowAddIdentifier] = useState(false)
  const [newIdentifier, setNewIdentifier] = useState({ type: 'phone', value: '' })

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get(`/contacts/${id}`),
      api.get(`/contacts/${id}/timeline`),
      api.get(`/contacts/${id}/identifiers`).catch(() => []),
    ])
      .then(([c, tl, ids]) => {
        setContact(c)
        setTimeline(tl)
        setIdentifiers(ids)
        setForm({
          name: c.name || '',
          email: c.email || '',
          notes: c.notes || '',
          tags: (c.tags || []).join(', '),
        })
      })
      .catch(e => {
        toast.error(e.message)
        navigate('/contacts')
      })
      .finally(() => setLoading(false))
  }, [id])

  // Cargar memorias cuando se activa la tab o cambia el filtro
  useEffect(() => {
    if (activeTab !== 'memoria') return
    setMemoriesLoading(true)
    const params = channelFilter ? `?channel=${channelFilter}&limit=50` : '?limit=50'
    api.get(`/contacts/${id}/memories${params}`)
      .then(setMemories)
      .catch(e => toast.error(e.message))
      .finally(() => setMemoriesLoading(false))
  }, [activeTab, channelFilter, id])

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updates = {
        name: form.name || null,
        email: form.email || null,
        notes: form.notes || null,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      }
      const updated = await api.patch(`/contacts/${id}`, updates)
      setContact(updated)
      toast.success('Contacto actualizado')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Eliminar contacto',
      message: '¿Eliminar este contacto? Esta acción es irreversible.',
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/contacts/${id}`)
      toast.success('Contacto eliminado')
      navigate('/contacts')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleAddIdentifier(e) {
    e.preventDefault()
    if (!newIdentifier.value.trim()) return
    try {
      const created = await api.post(`/contacts/${id}/identifiers`, {
        identifier_type: newIdentifier.type,
        identifier_value: newIdentifier.value.trim(),
      })
      setIdentifiers(prev => [...prev, created])
      setNewIdentifier({ type: 'phone', value: '' })
      setShowAddIdentifier(false)
      toast.success('Identificador agregado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <PageLoader />
  if (!contact) return null

  const calls = timeline?.calls || []
  const appointments = timeline?.appointments || []
  const campaignCalls = timeline?.campaign_calls || []
  const summary = timeline?.summary || {}
  const preferences = contact.preferences || {}
  const keyFacts = contact.key_facts || []
  const hasMemoryData = contact.summary || Object.keys(preferences).length > 0 || keyFacts.length > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate('/contacts')}>
          <ArrowLeft size={16} />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{contact.name || 'Sin nombre'}</h1>
          <div className="flex items-center gap-2 flex-wrap mt-1">
            {identifiers.length > 0 ? (
              identifiers.map(ident => {
                const Icon = IDENTIFIER_ICONS[ident.identifier_type] || Globe
                return (
                  <span key={ident.id} className="inline-flex items-center gap-1 text-xs bg-bg-secondary px-2 py-0.5 rounded-full text-text-secondary">
                    <Icon size={10} />
                    {ident.identifier_value}
                    {ident.is_primary && <span className="text-accent text-[9px]">*</span>}
                  </span>
                )
              })
            ) : (
              <span className="text-sm text-text-muted flex items-center gap-2">
                <Phone size={12} /> {contact.phone}
                {contact.email && <><Mail size={12} className="ml-2" /> {contact.email}</>}
              </span>
            )}
          </div>
        </div>
        {contact.average_sentiment && (
          <span className={`px-2 py-1 rounded text-xs font-medium ${SENTIMIENTO_COLORS[contact.average_sentiment] || ''}`}>
            {contact.average_sentiment}
          </span>
        )}
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6 text-sm flex-wrap">
        <span className="flex items-center gap-1">
          <PhoneCall size={14} className="text-accent" />
          <strong>{contact.call_count || summary.total_calls || 0}</strong> llamadas
        </span>
        <span className="flex items-center gap-1">
          <Calendar size={14} className="text-green-400" />
          <strong>{summary.total_appointments || 0}</strong> citas
        </span>
        {contact.lead_score > 0 && (
          <span className="flex items-center gap-1">
            <TrendingUp size={14} className="text-purple-400" />
            Lead: <strong>{contact.lead_score}/100</strong>
          </span>
        )}
        {contact.last_interaction_channel && (
          <span className="flex items-center gap-1 text-xs text-text-muted">
            {(() => {
              const ch = CHANNEL_ICONS[contact.last_interaction_channel]
              const ChIcon = ch?.icon || Globe
              return <><ChIcon size={12} className={ch?.color} /> {ch?.label || contact.last_interaction_channel}</>
            })()}
          </span>
        )}
        {summary.last_contact_date && (
          <span className="text-xs text-text-muted flex items-center gap-1">
            <Clock size={12} /> Último: {new Date(summary.last_contact_date).toLocaleDateString('es-MX')}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Formulario de edición + Memoria sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <h2 className="text-lg font-semibold mb-4">Información</h2>
            <form onSubmit={handleSave} className="space-y-4">
              <Input label="Nombre" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              <Input label="Email" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              <div>
                <label className="block text-xs text-text-muted mb-1">Notas</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm resize-y min-h-[80px] focus:outline-none focus:border-accent"
                  rows={3}
                />
              </div>
              <Input
                label="Tags (separados por coma)"
                value={form.tags}
                onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
                placeholder="vip, frecuente"
              />
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={saving} className="flex-1">
                  <Save size={14} className="mr-1" /> {saving ? 'Guardando...' : 'Guardar'}
                </Button>
                <Button variant="secondary" type="button" onClick={handleDelete} className="text-danger">
                  <Trash2 size={14} />
                </Button>
              </div>
            </form>

            {/* Meta */}
            <div className="mt-4 pt-4 border-t border-border space-y-2 text-xs text-text-muted">
              <p>Fuente: <Badge variant={contact.source === 'manual' ? 'client' : 'inbound'}>{contact.source}</Badge></p>
              <p>Creado: {contact.created_at ? new Date(contact.created_at).toLocaleString('es-MX') : '—'}</p>
              {contact.first_interaction_at && (
                <p>Primera interacción: {new Date(contact.first_interaction_at).toLocaleString('es-MX')}</p>
              )}
            </div>
          </Card>

          {/* Memoria del contacto — sidebar */}
          {hasMemoryData && (
            <Card>
              <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Brain size={14} className="text-purple-400" /> Memoria IA
              </h2>

              {contact.summary && (
                <div className="mb-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Resumen</p>
                  <p className="text-xs text-text-secondary leading-relaxed">{contact.summary}</p>
                </div>
              )}

              {Object.keys(preferences).length > 0 && (
                <div className="mb-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Preferencias</p>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(preferences).map(([k, v]) => (
                      <span key={k} className="inline-flex items-center gap-1 text-[10px] bg-purple-500/10 text-purple-300 px-1.5 py-0.5 rounded">
                        {k}: {String(v)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {keyFacts.length > 0 && (
                <div>
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Datos clave</p>
                  <ul className="space-y-1">
                    {keyFacts.map((fact, i) => (
                      <li key={i} className="text-xs text-text-secondary flex items-start gap-1">
                        <span className="text-accent mt-0.5">•</span> {String(fact)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          {/* Identificadores */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">Identificadores</h2>
              <button
                type="button"
                onClick={() => setShowAddIdentifier(!showAddIdentifier)}
                className="text-accent hover:text-accent/80 transition-colors cursor-pointer"
              >
                <Plus size={14} />
              </button>
            </div>

            {showAddIdentifier && (
              <form onSubmit={handleAddIdentifier} className="mb-3 p-2 bg-bg-primary rounded-lg space-y-2">
                <select
                  value={newIdentifier.type}
                  onChange={e => setNewIdentifier(p => ({ ...p, type: e.target.value }))}
                  className="w-full bg-bg-secondary border border-border rounded px-2 py-1 text-xs"
                >
                  <option value="phone">Teléfono</option>
                  <option value="email">Email</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="custom">Otro</option>
                </select>
                <Input
                  value={newIdentifier.value}
                  onChange={e => setNewIdentifier(p => ({ ...p, value: e.target.value }))}
                  placeholder="Valor del identificador"
                  className="text-xs"
                />
                <Button type="submit" className="w-full text-xs">Agregar</Button>
              </form>
            )}

            {identifiers.length === 0 ? (
              <p className="text-xs text-text-muted">Sin identificadores vinculados</p>
            ) : (
              <div className="space-y-1.5">
                {identifiers.map(ident => {
                  const Icon = IDENTIFIER_ICONS[ident.identifier_type] || Globe
                  return (
                    <div key={ident.id} className="flex items-center gap-2 text-xs">
                      <Icon size={12} className="text-text-muted flex-shrink-0" />
                      <span className="text-text-secondary truncate">{ident.identifier_value}</span>
                      <span className="text-[10px] text-text-muted">{ident.identifier_type}</span>
                      {ident.is_primary && <span className="text-[9px] text-accent">primario</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>

        {/* Tabs: Timeline / Llamadas / Citas / Memoria */}
        <Card className="lg:col-span-2">
          <div className="flex gap-1 mb-4 border-b border-border">
            {TABS.map(tab => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                  activeTab === tab.key
                    ? 'text-accent border-b-2 border-accent'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'timeline' && (
            <ContactTimeline
              calls={calls}
              appointments={appointments}
              campaignCalls={campaignCalls}
            />
          )}

          {activeTab === 'calls' && (
            calls.length === 0 ? (
              <p className="text-text-muted text-center py-8">Sin llamadas registradas</p>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Dirección</Th>
                    <Th>Duración</Th>
                    <Th>Estado</Th>
                    <Th>Sentimiento</Th>
                    <Th>Resumen</Th>
                    <Th>Fecha</Th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map(call => (
                    <tr
                      key={call.id}
                      className="hover:bg-bg-hover cursor-pointer transition-colors"
                      onClick={() => navigate(`/calls/${call.id}`)}
                    >
                      <Td><Badge variant={call.direction}>{call.direction}</Badge></Td>
                      <Td>
                        <span className="flex items-center gap-1 text-xs">
                          <Clock size={12} />
                          {Math.floor(call.duration_seconds / 60)}:{String(call.duration_seconds % 60).padStart(2, '0')}
                        </span>
                      </Td>
                      <Td><Badge variant={call.status}>{call.status}</Badge></Td>
                      <Td>
                        {call.sentimiento ? (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SENTIMIENTO_COLORS[call.sentimiento] || ''}`}>
                            {call.sentimiento}
                          </span>
                        ) : '—'}
                      </Td>
                      <Td>
                        <span className="text-xs text-text-secondary line-clamp-1">
                          {call.resumen_ia || call.summary || '—'}
                        </span>
                      </Td>
                      <Td>
                        <span className="text-xs text-text-muted">
                          {call.started_at ? new Date(call.started_at).toLocaleString('es-MX') : '—'}
                        </span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )
          )}

          {activeTab === 'appointments' && (
            appointments.length === 0 ? (
              <p className="text-text-muted text-center py-8">Sin citas registradas</p>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Título</Th>
                    <Th>Fecha</Th>
                    <Th>Estado</Th>
                    <Th>Descripción</Th>
                  </tr>
                </thead>
                <tbody>
                  {appointments.map(apt => (
                    <tr key={apt.id} className="hover:bg-bg-hover/50">
                      <Td className="font-medium">{apt.title}</Td>
                      <Td>
                        <span className="text-xs">
                          {apt.start_time ? new Date(apt.start_time).toLocaleString('es-MX') : '—'}
                        </span>
                      </Td>
                      <Td><Badge variant={apt.status}>{apt.status}</Badge></Td>
                      <Td>
                        <span className="text-xs text-text-secondary line-clamp-1">
                          {apt.description || '—'}
                        </span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )
          )}

          {activeTab === 'memoria' && (
            <div>
              {/* Channel filters */}
              <div className="flex gap-2 mb-4">
                {CHANNEL_FILTERS.map(cf => (
                  <button
                    key={cf.key || 'all'}
                    type="button"
                    onClick={() => setChannelFilter(cf.key)}
                    className={`px-3 py-1 text-xs rounded-full transition-colors cursor-pointer ${
                      channelFilter === cf.key
                        ? 'bg-accent/20 text-accent'
                        : 'bg-bg-secondary text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {cf.label}
                  </button>
                ))}
              </div>

              {memoriesLoading ? (
                <p className="text-text-muted text-center py-8">Cargando memorias...</p>
              ) : memories.length === 0 ? (
                <div className="text-center py-12">
                  <Brain size={32} className="mx-auto text-text-muted/30 mb-3" />
                  <p className="text-text-muted">Sin memorias registradas</p>
                  <p className="text-xs text-text-muted/60 mt-1">Las memorias se crean automáticamente al finalizar cada interacción</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {memories.map(mem => {
                    const ch = CHANNEL_ICONS[mem.channel] || CHANNEL_ICONS.call
                    const ChIcon = ch.icon
                    return (
                      <div key={mem.id} className="border border-border rounded-lg p-3 hover:bg-bg-hover/30 transition-colors">
                        {/* Header */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <ChIcon size={14} className={ch.color} />
                            <span className="text-xs font-medium">{ch.label}</span>
                            {mem.agent_name && (
                              <span className="text-[10px] text-text-muted">con {mem.agent_name}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {mem.sentiment && (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SENTIMIENTO_COLORS[mem.sentiment] || ''}`}>
                                {mem.sentiment}
                              </span>
                            )}
                            <span className="text-[10px] text-text-muted">
                              {mem.created_at ? new Date(mem.created_at).toLocaleDateString('es-MX', {
                                day: 'numeric', month: 'short', year: 'numeric',
                              }) : ''}
                            </span>
                          </div>
                        </div>

                        {/* Summary */}
                        <p className="text-sm text-text-secondary leading-relaxed mb-2">{mem.summary}</p>

                        {/* Topics */}
                        {mem.topics && mem.topics.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {mem.topics.map((topic, i) => (
                              <span key={i} className="text-[10px] bg-bg-secondary text-text-muted px-1.5 py-0.5 rounded">
                                {topic}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Action items */}
                        {mem.action_items && mem.action_items.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-border/50">
                            <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pendientes</p>
                            {mem.action_items.map((item, i) => (
                              <p key={i} className="text-xs text-text-secondary flex items-start gap-1">
                                <span className="text-yellow-400 mt-0.5">○</span> {item}
                              </p>
                            ))}
                          </div>
                        )}

                        {/* Duration */}
                        {mem.duration_seconds > 0 && (
                          <p className="text-[10px] text-text-muted mt-2">
                            Duración: {Math.floor(mem.duration_seconds / 60)}:{String(mem.duration_seconds % 60).padStart(2, '0')}
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
