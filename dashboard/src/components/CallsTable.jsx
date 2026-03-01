import { useNavigate } from 'react-router-dom'
import { Phone, PhoneOutgoing } from 'lucide-react'
import { Badge } from './ui/Badge'
import { Table, Th, Td } from './ui/Table'

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleDateString('es-MX', { month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
}

export function CallsTable({ calls = [] }) {
  const navigate = useNavigate()

  if (!calls.length) {
    return <p className="text-text-muted text-sm py-8 text-center">Sin llamadas registradas</p>
  }

  return (
    <Table>
      <thead>
        <tr>
          <Th></Th>
          <Th>De / Para</Th>
          <Th>Agente</Th>
          <Th>Duración</Th>
          <Th>Estado</Th>
          <Th>Fecha</Th>
          <Th>Costo</Th>
        </tr>
      </thead>
      <tbody>
        {calls.map(call => (
          <tr
            key={call.id}
            onClick={() => navigate(`/calls/${call.id}`)}
            className="hover:bg-bg-hover/50 cursor-pointer transition-colors"
          >
            <Td>
              {call.direction === 'inbound'
                ? <Phone size={16} className="text-accent" />
                : <PhoneOutgoing size={16} className="text-purple-400" />}
            </Td>
            <Td className="font-mono text-xs">
              {call.caller_number || call.callee_number || '-'}
            </Td>
            <Td className="text-xs text-text-secondary">{call.agent_name || '-'}</Td>
            <Td className="font-mono">{formatDuration(call.duration_seconds)}</Td>
            <Td><Badge variant={call.status}>{call.status}</Badge></Td>
            <Td className="text-text-secondary text-xs">{formatDate(call.started_at)}</Td>
            <Td className="font-mono text-xs">${Number(call.cost_total).toFixed(4)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
