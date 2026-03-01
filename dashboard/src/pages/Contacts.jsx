import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { UserPlus, Search, Phone, Mail, PhoneCall, Clock, Trash2, Pencil } from 'lucide-react'

const sourceLabels = {
  inbound_call: 'Llamada entrante',
  outbound_call: 'Llamada saliente',
  manual: 'Manual',
  whatsapp: 'WhatsApp',
  phone_contact: 'Teléfono',
}

export function Contacts() {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [clientId, setClientId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [editingContact, setEditingContact] = useState(null)
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  function loadContacts() {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (search) params.set('search', search)
    if (clientId) params.set('client_id', clientId)
    api.get(`/contacts?${params}`)
      .then(setContacts)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadContacts() }, [page, search, clientId])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
  }

  async function handleDelete(e, contact) {
    e.stopPropagation()
    const ok = await confirm({
      title: 'Eliminar contacto',
      message: `¿Eliminar a ${contact.name || contact.phone}? Se borrarán también todas sus llamadas, memorias y citas. Esta acción es irreversible.`,
      confirmText: 'Eliminar todo',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/contacts/${contact.id}`)
      setContacts(prev => prev.filter(c => c.id !== contact.id))
      toast.success('Contacto y su historial eliminados')
    } catch (err) {
      toast.error(err.message)
    }
  }

  function handleEdit(e, contact) {
    e.stopPropagation()
    setEditingContact(contact)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Contactos</h1>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={v => { setClientId(v); setPage(1) }} />
          <Button onClick={() => setShowCreate(true)}>
            <UserPlus size={16} className="mr-1" /> Nuevo
          </Button>
        </div>
      </div>

      {/* Barra de búsqueda */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <Input
            placeholder="Buscar por nombre, teléfono o email..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </form>

      <Card>
        {loading ? (
          <PageLoader />
        ) : contacts.length === 0 ? (
          <p className="text-text-muted text-center py-8">No hay contactos</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Nombre</Th>
                <Th>Teléfono</Th>
                <Th>Email</Th>
                <Th>Llamadas</Th>
                <Th>Último contacto</Th>
                <Th>Fuente</Th>
                <Th className="w-20">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => (
                <tr
                  key={c.id}
                  className="hover:bg-bg-hover cursor-pointer transition-colors"
                  onClick={() => navigate(`/contacts/${c.id}`)}
                >
                  <Td>
                    <span className="font-medium">{c.name || 'Sin nombre'}</span>
                    {c.tags?.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {c.tags.map(t => (
                          <span key={t} className="text-[10px] bg-accent/10 text-accent px-1.5 rounded">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </Td>
                  <Td>
                    <span className="flex items-center gap-1 font-mono text-xs">
                      <Phone size={12} className="text-text-muted" /> {c.phone}
                    </span>
                  </Td>
                  <Td>
                    {c.email ? (
                      <span className="flex items-center gap-1 text-xs">
                        <Mail size={12} className="text-text-muted" /> {c.email}
                      </span>
                    ) : (
                      <span className="text-text-muted text-xs">—</span>
                    )}
                  </Td>
                  <Td>
                    <span className="flex items-center gap-1 text-xs font-mono">
                      <PhoneCall size={12} className="text-text-muted" />
                      {c.call_count || 0}
                    </span>
                  </Td>
                  <Td>
                    <span className="flex items-center gap-1 text-xs text-text-muted">
                      <Clock size={12} />
                      {c.last_call_at ? new Date(c.last_call_at).toLocaleDateString('es-MX') : '—'}
                    </span>
                  </Td>
                  <Td>
                    <Badge variant={c.source === 'manual' ? 'client' : 'inbound'}>
                      {sourceLabels[c.source] || c.source}
                    </Badge>
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={e => handleEdit(e, c)}
                        className="p-1.5 rounded hover:bg-bg-secondary text-text-muted hover:text-accent transition-colors cursor-pointer"
                        title="Editar"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={e => handleDelete(e, c)}
                        className="p-1.5 rounded hover:bg-red-500/10 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
                        title="Eliminar"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {/* Paginación */}
      <div className="flex justify-center gap-2">
        <Button variant="secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
          Anterior
        </Button>
        <span className="px-4 py-2 text-sm text-text-muted">Página {page}</span>
        <Button variant="secondary" onClick={() => setPage(p => p + 1)} disabled={contacts.length < 20}>
          Siguiente
        </Button>
      </div>

      {/* Modal crear contacto */}
      {showCreate && (
        <CreateContactModal
          onClose={() => setShowCreate(false)}
          onCreated={c => {
            setContacts(prev => [c, ...prev])
            setShowCreate(false)
            toast.success('Contacto creado')
          }}
        />
      )}

      {/* Modal editar contacto */}
      {editingContact && (
        <EditContactModal
          contact={editingContact}
          onClose={() => setEditingContact(null)}
          onSaved={updated => {
            setContacts(prev => prev.map(c => c.id === updated.id ? updated : c))
            setEditingContact(null)
            toast.success('Contacto actualizado')
          }}
        />
      )}
    </div>
  )
}

function CreateContactModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', phone: '', email: '', notes: '' })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.phone) return toast.error('Teléfono requerido')
    setSaving(true)
    try {
      const created = await api.post('/contacts', form)
      onCreated(created)
    } catch (err) {
      if (err.message?.includes('409') || err.message?.includes('Ya existe')) {
        toast.error('Ya existe un contacto con ese teléfono')
      } else {
        toast.error(err.message)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Nuevo contacto" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Nombre" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        <Input label="Teléfono *" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} required />
        <Input label="Email" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
        <Input label="Notas" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Crear'}</Button>
        </div>
      </form>
    </Modal>
  )
}

function EditContactModal({ contact, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: contact.name || '',
    email: contact.email || '',
    notes: contact.notes || '',
    tags: (contact.tags || []).join(', '),
  })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const updates = {
        name: form.name || null,
        email: form.email || null,
        notes: form.notes || null,
        tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      }
      const updated = await api.patch(`/contacts/${contact.id}`, updates)
      onSaved(updated)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Editar contacto" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="text-xs text-text-muted mb-2">
          <Phone size={12} className="inline mr-1" />
          {contact.phone}
        </div>
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
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</Button>
        </div>
      </form>
    </Modal>
  )
}
