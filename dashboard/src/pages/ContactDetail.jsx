import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../context/ToastContext'
import { ArrowLeft, Save, Phone, Mail, Clock, Trash2 } from 'lucide-react'

export function ContactDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [contact, setContact] = useState(null)
  const [calls, setCalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', notes: '', tags: '' })

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get(`/contacts/${id}`),
      api.get(`/contacts/${id}/calls`),
    ])
      .then(([c, callsList]) => {
        setContact(c)
        setCalls(callsList)
        setForm({
          name: c.name || '',
          email: c.email || '',
          notes: c.notes || '',
          tags: (c.tags || []).join(', '),
        })
      })
      .catch(e => {
        toast(e.message, 'error')
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
      toast('Contacto actualizado')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!confirm('¿Eliminar este contacto?')) return
    try {
      await api.delete(`/contacts/${id}`)
      toast('Contacto eliminado')
      navigate('/contacts')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  if (loading) return <PageLoader />
  if (!contact) return null

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

        {/* Historial de llamadas */}
        <Card className="lg:col-span-2">
          <h2 className="text-lg font-semibold mb-4">Historial de llamadas</h2>
          {calls.length === 0 ? (
            <p className="text-text-muted text-center py-8">Sin llamadas registradas</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Dirección</Th>
                  <Th>Duración</Th>
                  <Th>Estado</Th>
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
                      <span className="text-xs text-text-secondary line-clamp-1">
                        {call.summary || '—'}
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
          )}
        </Card>
      </div>
    </div>
  )
}
