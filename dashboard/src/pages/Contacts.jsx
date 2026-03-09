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
import { FilterBar } from '../components/FilterBar'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { UserPlus, Search, Phone, Mail, PhoneCall, Clock, Trash2, Pencil, Users, Download, Upload } from 'lucide-react'
import { EmptyState } from '../components/EmptyState'

const SOURCE_OPTIONS = [
  { value: 'inbound_call', label: 'Llamada entrante' },
  { value: 'outbound_call', label: 'Llamada saliente' },
  { value: 'manual', label: 'Manual' },
  { value: 'whatsapp', label: 'WhatsApp' },
]

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
  const [sourceFilter, setSourceFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [clientId, setClientId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [editingContact, setEditingContact] = useState(null)
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  function loadContacts() {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 20 })
    if (search) params.set('search', search)
    if (clientId) params.set('client_id', clientId)
    if (sourceFilter) params.set('source', sourceFilter)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    api.get(`/contacts?${params}`)
      .then(setContacts)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadContacts() }, [page, search, clientId, sourceFilter, dateFrom, dateTo])

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
          <Button
            variant="secondary"
            onClick={() => {
              const params = new URLSearchParams()
              if (clientId) params.set('client_id', clientId)
              api.download(`/contacts/export/csv?${params}`).catch(e => toast.error(e.message))
            }}
            className="text-xs"
            title="Exportar a CSV"
          >
            <Download size={14} className="mr-1" /> CSV
          </Button>
          <Button
            variant="secondary"
            onClick={() => setShowImport(true)}
            className="text-xs"
            title="Importar CSV"
          >
            <Upload size={14} className="mr-1" /> Importar
          </Button>
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

      <FilterBar
        filters={[
          { key: 'source', label: 'Fuente', options: SOURCE_OPTIONS },
        ]}
        values={{ source: sourceFilter }}
        onChange={(key, value) => { setSourceFilter(value); setPage(1) }}
        dateRange
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateChange={(from, to) => { setDateFrom(from); setDateTo(to); setPage(1) }}
        onClear={() => { setSourceFilter(''); setDateFrom(''); setDateTo(''); setPage(1) }}
      />

      <Card>
        {loading ? (
          <PageLoader />
        ) : contacts.length === 0 ? (
          <EmptyState
            icon={Users}
            title={search ? 'Sin resultados' : 'Sin contactos'}
            description={search
              ? `No se encontraron contactos para "${search}". Intenta con otro termino.`
              : 'Los contactos se crean automaticamente cuando recibes llamadas o mensajes. Tambien puedes agregarlos manualmente.'
            }
            action={!search ? () => setShowCreate(true) : undefined}
            actionLabel={!search ? 'Agregar contacto' : undefined}
            actionIcon={!search ? UserPlus : undefined}
          />
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

      {/* Modal importar CSV */}
      {showImport && (
        <ImportContactsModal
          onClose={() => setShowImport(false)}
          onImported={() => {
            setShowImport(false)
            loadContacts()
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

function ImportContactsModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const toast = useToast()

  function downloadTemplate() {
    const csv = 'nombre,telefono,email,notas,tags\nJuan Pérez,+5215551234567,juan@email.com,Cliente VIP,"vip, frecuente"\nMaría López,5219994567890,,,nuevo\n'
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'plantilla_contactos.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleUpload() {
    if (!file) return toast.error('Selecciona un archivo CSV')
    setUploading(true)
    setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.upload('/contacts/import/csv', formData)
      setResult(res)
      if (res.imported > 0) {
        toast.success(`${res.imported} contactos importados`)
      }
    } catch (err) {
      toast.error(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Modal open={true} title="Importar contactos desde CSV" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-text-muted">
          Sube un archivo CSV con las columnas: <span className="font-mono text-xs">nombre, telefono, email, notas, tags</span>.
          Máximo 1,000 filas. Los contactos duplicados (mismo teléfono) se omiten.
        </p>

        <button
          type="button"
          onClick={downloadTemplate}
          className="text-xs text-accent hover:underline cursor-pointer"
        >
          <Download size={12} className="inline mr-1" />
          Descargar plantilla CSV
        </button>

        <div>
          <label className="block text-xs text-text-muted mb-1">Archivo CSV</label>
          <input
            type="file"
            accept=".csv"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-text-secondary file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-accent/10 file:text-accent file:cursor-pointer hover:file:bg-accent/20"
          />
        </div>

        {result && (
          <div className="bg-bg-primary border border-border rounded-lg p-3 space-y-1">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-green-400 font-medium">Importados: {result.imported}</span>
              <span className="text-yellow-400">Omitidos: {result.skipped}</span>
              {result.errors?.length > 0 && (
                <span className="text-red-400">Errores: {result.errors.length}</span>
              )}
            </div>
            {result.errors?.length > 0 && (
              <div className="mt-2 max-h-32 overflow-y-auto">
                {result.errors.map((err, i) => (
                  <p key={i} className="text-xs text-red-400">{err}</p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          {result ? (
            <Button onClick={onImported}>Cerrar</Button>
          ) : (
            <>
              <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
              <Button onClick={handleUpload} disabled={uploading || !file}>
                <Upload size={14} className="mr-1" />
                {uploading ? 'Importando...' : 'Importar'}
              </Button>
            </>
          )}
        </div>
      </div>
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
