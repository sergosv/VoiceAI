import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Users, Power, PowerOff, Trash2, Pencil } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'

export function ClientsList() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()

  useEffect(() => {
    let cancelled = false
    api.get('/clients')
      .then(data => { if (!cancelled) setClients(data) })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function handleToggleActive(e, client) {
    e.stopPropagation()
    try {
      const updated = await api.patch(`/clients/${client.id}`, { is_active: !client.is_active })
      setClients(prev => prev.map(c => c.id === client.id ? updated : c))
      toast.success(`${client.name} ${updated.is_active ? 'activado' : 'desactivado'}`)
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete(e, client) {
    e.stopPropagation()
    const ok = await confirm({
      title: 'Eliminar cliente',
      message: `Eliminar ${client.name}? Se borraran todos sus datos, agentes, llamadas y documentos.`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${client.id}`)
      setClients(prev => prev.filter(c => c.id !== client.id))
      toast.success('Cliente eliminado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Clientes</h1>
        <Button onClick={() => navigate('/admin/clients/new')}>
          <Plus size={16} className="mr-2 inline" /> Nuevo cliente
        </Button>
      </div>

      <Card>
        {loading ? <PageLoader /> : clients.length === 0 ? (
          <div className="text-center py-12">
            <Users size={40} className="mx-auto text-text-muted mb-3" />
            <p className="text-text-muted">Sin clientes registrados.</p>
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Nombre</Th>
                <Th>Slug</Th>
                <Th>Tipo</Th>
                <Th>Estado</Th>
                <Th className="text-right">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {clients.map(c => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/admin/clients/${c.id}`)}
                  className="hover:bg-bg-hover/50 cursor-pointer transition-colors"
                >
                  <Td>
                    <div>
                      <span className="font-medium">{c.name}</span>
                      {c.owner_email && (
                        <p className="text-[11px] text-text-muted truncate max-w-[200px]">{c.owner_email}</p>
                      )}
                    </div>
                  </Td>
                  <Td className="font-mono text-xs text-text-secondary">{c.slug}</Td>
                  <Td><Badge>{c.business_type}</Badge></Td>
                  <Td>
                    <Badge variant={c.is_active ? 'completed' : 'failed'}>
                      {c.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={(e) => handleToggleActive(e, c)}
                        className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                          c.is_active
                            ? 'text-success hover:bg-success/10'
                            : 'text-text-muted hover:bg-bg-hover'
                        }`}
                        title={c.is_active ? 'Desactivar' : 'Activar'}
                      >
                        {c.is_active ? <Power size={15} /> : <PowerOff size={15} />}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/admin/clients/${c.id}`) }}
                        className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors cursor-pointer"
                        title="Editar"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, c)}
                        className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                        title="Eliminar"
                      >
                        <Trash2 size={15} />
                      </button>
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
