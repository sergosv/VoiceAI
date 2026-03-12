import { useEffect, useState } from 'react'
import { Users, Pencil, X, Check, Loader2, RefreshCw } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

export function AdminUsers() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function fetchUsers() {
    try {
      const data = await api.get('/admin/users')
      setUsers(data)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    api.get('/admin/users')
      .then(data => { if (!cancelled) setUsers(data) })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  function startEdit(user) {
    setEditingId(user.id)
    setEditForm({
      display_name: user.display_name || '',
      role: user.role || 'client',
      is_active: user.is_active !== false,
    })
  }

  function cancelEdit() {
    setEditingId(null)
    setEditForm({})
  }

  async function saveEdit(userId) {
    setSaving(true)
    try {
      const updated = await api.patch(`/admin/users/${userId}`, editForm)
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, ...updated } : u))
      setEditingId(null)
      toast.success('Usuario actualizado')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Users size={22} className="text-accent" />
            Usuarios
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {users.length} usuario{users.length !== 1 ? 's' : ''} registrado{users.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => { setLoading(true); fetchUsers() }}
        >
          <RefreshCw size={14} className="mr-2 inline" />
          Actualizar
        </Button>
      </div>

      <Card>
        {loading ? <PageLoader /> : users.length === 0 ? (
          <EmptyState
            icon={Users}
            title="Sin usuarios"
            description="No hay usuarios registrados en la plataforma."
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Email</Th>
                <Th>Nombre</Th>
                <Th>Rol</Th>
                <Th>Cliente</Th>
                <Th>Estado</Th>
                <Th>Creado</Th>
                <Th className="text-right">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} className="hover:bg-bg-hover/50 transition-colors">
                  <Td>
                    <span className="text-text-primary text-xs font-mono">{user.email}</span>
                  </Td>
                  <Td>
                    {editingId === user.id ? (
                      <input
                        type="text"
                        value={editForm.display_name}
                        onChange={e => setEditForm(f => ({ ...f, display_name: e.target.value }))}
                        className="bg-bg-secondary border border-border rounded-lg px-2 py-1 text-sm text-text-primary w-full focus:border-accent focus:outline-none"
                        placeholder="Nombre"
                      />
                    ) : (
                      <span className="text-text-primary text-sm">
                        {user.display_name || <span className="text-text-muted italic">Sin nombre</span>}
                      </span>
                    )}
                  </Td>
                  <Td>
                    {editingId === user.id ? (
                      <select
                        value={editForm.role}
                        onChange={e => setEditForm(f => ({ ...f, role: e.target.value }))}
                        className="bg-bg-secondary border border-border rounded-lg px-2 py-1 text-sm text-text-primary focus:border-accent focus:outline-none cursor-pointer"
                      >
                        <option value="admin">admin</option>
                        <option value="client">client</option>
                      </select>
                    ) : (
                      <Badge variant={user.role === 'admin' ? 'admin' : 'client'}>
                        {user.role || 'client'}
                      </Badge>
                    )}
                  </Td>
                  <Td>
                    <span className="text-text-secondary text-xs">
                      {user.client_name || <span className="text-text-muted">--</span>}
                    </span>
                  </Td>
                  <Td>
                    {editingId === user.id ? (
                      <button
                        onClick={() => setEditForm(f => ({ ...f, is_active: !f.is_active }))}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer ${
                          editForm.is_active ? 'bg-accent/40' : 'bg-bg-secondary'
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 rounded-full transition-transform ${
                            editForm.is_active
                              ? 'translate-x-[18px] bg-accent'
                              : 'translate-x-[3px] bg-text-muted'
                          }`}
                        />
                      </button>
                    ) : (
                      <Badge variant={user.is_active !== false ? 'completed' : 'failed'}>
                        {user.is_active !== false ? 'Activo' : 'Inactivo'}
                      </Badge>
                    )}
                  </Td>
                  <Td>
                    <span className="text-text-muted text-xs">
                      {user.created_at
                        ? new Date(user.created_at).toLocaleDateString('es-MX', {
                            day: '2-digit', month: 'short', year: 'numeric',
                          })
                        : '--'}
                    </span>
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end gap-1">
                      {editingId === user.id ? (
                        <>
                          <button
                            onClick={() => saveEdit(user.id)}
                            disabled={saving}
                            className="p-1.5 rounded-lg text-success hover:bg-success/10 transition-colors cursor-pointer disabled:opacity-50"
                            title="Guardar"
                          >
                            {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                            title="Cancelar"
                          >
                            <X size={15} />
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => startEdit(user)}
                          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors cursor-pointer"
                          title="Editar"
                        >
                          <Pencil size={15} />
                        </button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
