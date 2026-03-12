import { useEffect, useState } from 'react'
import { Phone, RefreshCw } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

export function AdminPhones() {
  const [phones, setPhones] = useState([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  async function fetchPhones() {
    try {
      const data = await api.get('/admin/phone-numbers')
      setPhones(data || [])
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.get('/admin/phone-numbers')
      .then(data => { if (!cancelled) setPhones(data || []) })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  function truncate(str, len = 16) {
    if (!str) return '--'
    return str.length > len ? str.slice(0, len) + '...' : str
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Phone size={22} className="text-accent" />
            Telefonos
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {phones.length} numero{phones.length !== 1 ? 's' : ''} asignado{phones.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => { setLoading(true); fetchPhones() }}
        >
          <RefreshCw size={14} className="mr-2 inline" />
          Actualizar
        </Button>
      </div>

      <Card>
        {loading ? <PageLoader /> : phones.length === 0 ? (
          <EmptyState
            icon={Phone}
            title="Sin telefonos asignados"
            description="No hay numeros de telefono asignados a agentes."
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Telefono</Th>
                <Th>Agente</Th>
                <Th>Cliente</Th>
                <Th>Tipo</Th>
                <Th>Trunk ID</Th>
                <Th>Estado</Th>
              </tr>
            </thead>
            <tbody>
              {phones.map(p => (
                <tr key={p.agent_id} className="hover:bg-bg-hover/50 transition-colors">
                  <Td>
                    <span className="font-mono text-sm text-text-primary">{p.phone_number}</span>
                  </Td>
                  <Td>
                    <span className="text-text-secondary text-sm">{p.agent_name}</span>
                  </Td>
                  <Td>
                    <span className="text-text-primary text-sm">{p.client_name}</span>
                  </Td>
                  <Td>
                    <Badge variant={p.agent_type === 'outbound' ? 'warning' : 'info'}>
                      {p.agent_type || 'inbound'}
                    </Badge>
                  </Td>
                  <Td>
                    <span className="font-mono text-xs text-text-muted" title={p.livekit_sip_trunk_id || ''}>
                      {truncate(p.livekit_sip_trunk_id)}
                    </span>
                  </Td>
                  <Td>
                    <Badge variant={p.is_active ? 'completed' : 'failed'}>
                      {p.is_active ? 'Activo' : 'Inactivo'}
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
