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
import { ArrowLeft, Save, Phone, Mail, Clock, Trash2, PhoneCall, TrendingUp, Calendar } from 'lucide-react'

const TABS = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'calls', label: 'Llamadas' },
  { key: 'appointments', label: 'Citas' },
]

const SENTIMIENTO_COLORS = {
  positivo: 'bg-green-500/20 text-green-400',
  neutral: 'bg-yellow-500/20 text-yellow-400',
  negativo: 'bg-red-500/20 text-red-400',
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

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get(`/contacts/${id}`),
      api.get(`/contacts/${id}/timeline`),
    ])
      .then(([c, tl]) => {
        setContact(c)
        setTimeline(tl)
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

  if (loading) return <PageLoader />
  if (!contact) return null

  const calls = timeline?.calls || []
  const appointments = timeline?.appointments || []
  const campaignCalls = timeline?.campaign_calls || []
  const summary = timeline?.summary || {}

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate('/contacts')}>
          <ArrowLeft size={16} />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{contact.name || 'Sin nombre'}</h1>
          <p className="text-sm text-text-muted flex items-center gap-2">
            <Phone size={12} /> {contact.phone}
            {contact.email && <><Mail size={12} className="ml-2" /> {contact.email}</>}
          </p>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6 text-sm">
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
        {summary.last_contact_date && (
          <span className="text-xs text-text-muted flex items-center gap-1">
            <Clock size={12} /> Último: {new Date(summary.last_contact_date).toLocaleDateString('es-MX')}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Formulario de edición */}
        <Card className="lg:col-span-1">
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
          </div>
        </Card>

        {/* Tabs: Timeline / Llamadas / Citas */}
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
        </Card>
      </div>
    </div>
  )
}
