import { useNavigate } from 'react-router-dom'
import { Phone, PhoneOutgoing, Mic } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
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
  const { user, impersonatingClientId } = useAuth()
  const isAdmin = user?.role === 'admin' && !impersonatingClientId

  if (!calls.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-xl bg-bg-secondary border border-border flex items-center justify-center mb-4">
          <Phone size={20} className="text-text-muted" />
        </div>
        <p className="text-sm font-medium text-text-secondary mb-1">Sin llamadas registradas</p>
        <p className="text-xs text-text-muted">Las llamadas apareceran aqui cuando tu agente reciba o haga llamadas</p>
      </div>
    )
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
          <Th>{isAdmin ? 'Costo' : 'Creditos'}</Th>
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
              <span className="flex items-center gap-1.5">
                {call.direction === 'inbound'
                  ? <Phone size={16} className="text-accent" />
                  : <PhoneOutgoing size={16} className="text-purple-400" />}
                {call.has_recording && (
                  <Mic size={12} className="text-accent/60" title="Tiene grabacion" />
                )}
              </span>
            </Td>
            <Td className="font-mono text-xs">
              {call.caller_number || call.callee_number || '-'}
            </Td>
            <Td className="text-xs text-text-secondary">{call.agent_name || '-'}</Td>
            <Td className="font-mono">{formatDuration(call.duration_seconds)}</Td>
            <Td><Badge variant={call.status}>{call.status}</Badge></Td>
            <Td className="text-text-secondary text-xs">{formatDate(call.started_at)}</Td>
            <Td className="font-mono text-xs">
              {isAdmin
                ? `$${Number(call.cost_total).toFixed(4)}`
                : `${(call.duration_seconds / 60).toFixed(1)}`
              }
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
