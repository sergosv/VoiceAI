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
import { UserPlus, Search, Phone, Mail } from 'lucide-react'

const sourceLabels = {
  inbound_call: 'Llamada entrante',
  outbound_call: 'Llamada saliente',
  manual: 'Manual',
  whatsapp: 'WhatsApp',
}

export function Contacts() {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [clientId, setClientId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (search) params.set('search', search)
    if (clientId) params.set('client_id', clientId)
    api.get(`/contacts?${params}`)
      .then(setContacts)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [page, search, clientId])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
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
                <Th>Fuente</Th>
                <Th>Fecha</Th>
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
                    <Badge variant={c.source === 'manual' ? 'client' : 'inbound'}>
                      {sourceLabels[c.source] || c.source}
                    </Badge>
                  </Td>
                  <Td>
                    <span className="text-xs text-text-muted">
                      {c.created_at ? new Date(c.created_at).toLocaleDateString('es-MX') : '—'}
                    </span>
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
      toast.error(err.message)
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
