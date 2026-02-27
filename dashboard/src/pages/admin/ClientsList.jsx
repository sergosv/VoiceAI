import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Phone, Users } from 'lucide-react'
import { api } from '../../lib/api'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'

export function ClientsList() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/clients')
      .then(setClients)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

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
                <Th>Agente</Th>
                <Th>Teléfono</Th>
                <Th>Tipo</Th>
                <Th>Estado</Th>
              </tr>
            </thead>
            <tbody>
              {clients.map(c => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/admin/clients/${c.id}`)}
                  className="hover:bg-bg-hover/50 cursor-pointer transition-colors"
                >
                  <Td className="font-medium">{c.name}</Td>
                  <Td className="font-mono text-xs text-text-secondary">{c.slug}</Td>
                  <Td>{c.agent_name}</Td>
                  <Td className="font-mono text-xs">{c.phone_number || '-'}</Td>
                  <Td><Badge>{c.business_type}</Badge></Td>
                  <Td>
                    <Badge variant={c.is_active ? 'completed' : 'failed'}>
                      {c.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
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
