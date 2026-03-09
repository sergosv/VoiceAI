import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { useAuth } from '../context/AuthContext'
import {
  Zap, Plus, Trash2, XCircle, Phone, MessageSquare, Send,
  Clock, CheckCircle2, AlertTriangle, Ban, BarChart3,
} from 'lucide-react'

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pendiente' },
  { value: 'executed', label: 'Ejecutada' },
  { value: 'failed', label: 'Fallida' },
  { value: 'cancelled', label: 'Cancelada' },
]

const CHANNEL_OPTIONS = [
  { value: 'call', label: 'Llamada' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'sms', label: 'SMS' },
]

const statusLabels = {
  pending: 'Pendiente',
  executed: 'Ejecutada',
  failed: 'Fallida',
  cancelled: 'Cancelada',
}

const statusBadgeVariant = {
  pending: 'pending',
  executed: 'completed',
  failed: 'failed',
  cancelled: 'cancelled',
}

const channelLabels = {
  call: 'Llamada',
  whatsapp: 'WhatsApp',
  sms: 'SMS',
}

const channelIcons = {
  call: Phone,
  whatsapp: MessageSquare,
  sms: Send,
}

const ruleTypeLabels = {
  callback_missed_call: 'Callback perdida',
  followup_no_conversion: 'Seguimiento',
  reminder_appointment: 'Recordatorio cita',
  post_sale: 'Post-venta',
  reengagement: 'Reengagement',
  custom: 'Personalizado',
}

const RULE_TYPE_OPTIONS = [
  { value: 'callback_missed_call', label: 'Callback perdida' },
  { value: 'followup_no_conversion', label: 'Seguimiento' },
  { value: 'reminder_appointment', label: 'Recordatorio cita' },
  { value: 'post_sale', label: 'Post-venta' },
  { value: 'reengagement', label: 'Reengagement' },
  { value: 'custom', label: 'Personalizado' },
]

export function ProactiveActions() {
  const [actions, setActions] = useState([])
  const [stats, setStats] = useState(null)
  const [agents, setAgents] = useState([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()

  const clientId = user?.client_id

  // Cargar agentes del cliente
  useEffect(() => {
    if (!clientId) return
    api.get(`/clients/${clientId}/agents`)
      .then(data => {
        setAgents(data)
        if (data.length > 0) {
          setSelectedAgentId(data[0].id)
        }
      })
      .catch(e => toast.error(e.message))
  }, [clientId])

  // Cargar acciones cuando cambia agente o filtros
  useEffect(() => {
    if (!selectedAgentId) {
      setLoading(false)
      return
    }
    loadActions()
  }, [selectedAgentId, statusFilter, channelFilter])

  // Cargar stats
  useEffect(() => {
    api.get('/proactive/scheduled-actions/stats')
      .then(setStats)
      .catch(() => {})
  }, [actions])

  function loadActions() {
    setLoading(true)
    const params = new URLSearchParams({ limit: '50' })
    if (statusFilter) params.set('status', statusFilter)
    if (channelFilter) params.set('channel', channelFilter)
    api.get(`/proactive/agents/${selectedAgentId}/scheduled-actions?${params}`)
      .then(setActions)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  async function handleCancel(action) {
    const ok = await confirm({
      title: 'Cancelar accion',
      message: `¿Cancelar la accion programada para ${action.target_number}?`,
      confirmText: 'Cancelar accion',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.patch(`/proactive/scheduled-actions/${action.id}`, { status: 'cancelled' })
      setActions(prev => prev.map(a => a.id === action.id ? { ...a, status: 'cancelled' } : a))
      toast.success('Accion cancelada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete(action) {
    const ok = await confirm({
      title: 'Eliminar accion',
      message: `¿Eliminar esta accion permanentemente?`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/proactive/scheduled-actions/${action.id}`)
      setActions(prev => prev.filter(a => a.id !== action.id))
      toast.success('Accion eliminada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const statCards = [
    { label: 'Total', value: stats?.total ?? 0, icon: BarChart3, color: 'text-accent' },
    { label: 'Pendientes', value: stats?.by_status?.pending ?? 0, icon: Clock, color: 'text-warning' },
    { label: 'Ejecutadas', value: stats?.by_status?.executed ?? 0, icon: CheckCircle2, color: 'text-success' },
    { label: 'Fallidas', value: stats?.by_status?.failed ?? 0, icon: AlertTriangle, color: 'text-danger' },
    { label: 'Canceladas', value: stats?.by_status?.cancelled ?? 0, icon: Ban, color: 'text-text-muted' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Acciones proactivas</h1>
        <div className="flex items-center gap-3">
          {/* Selector de agente */}
          {agents.length > 1 && (
            <select
              value={selectedAgentId}
              onChange={e => setSelectedAgentId(e.target.value)}
              className="bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
            >
              {agents.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          )}
          <Button onClick={() => setShowCreate(true)} disabled={!selectedAgentId}>
            <Plus size={16} className="mr-1" /> Nueva accion
          </Button>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {statCards.map(s => {
            const Icon = s.icon
            return (
              <Card key={s.label} className="flex items-center gap-3 !p-4">
                <div className={`w-10 h-10 rounded-lg bg-bg-secondary flex items-center justify-center ${s.color}`}>
                  <Icon size={20} />
                </div>
                <div>
                  <p className="text-2xl font-bold">{s.value}</p>
                  <p className="text-xs text-text-muted">{s.label}</p>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Filtros */}
      <FilterBar
        filters={[
          { key: 'status', label: 'Estado', options: STATUS_OPTIONS },
          { key: 'channel', label: 'Canal', options: CHANNEL_OPTIONS },
        ]}
        values={{ status: statusFilter, channel: channelFilter }}
        onChange={(key, value) => {
          if (key === 'status') setStatusFilter(value)
          if (key === 'channel') setChannelFilter(value)
        }}
        onClear={() => { setStatusFilter(''); setChannelFilter('') }}
      />

      {/* Tabla */}
      <Card>
        {loading ? (
          <PageLoader />
        ) : !selectedAgentId ? (
          <EmptyState
            icon={Zap}
            title="Sin agentes"
            description="No se encontraron agentes para este cliente. Crea un agente primero para programar acciones proactivas."
          />
        ) : actions.length === 0 ? (
          <EmptyState
            icon={Zap}
            title="Sin acciones programadas"
            description="Las acciones proactivas permiten programar callbacks, seguimientos y recordatorios automaticos."
            action={() => setShowCreate(true)}
            actionLabel="Nueva accion"
            actionIcon={Plus}
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Tipo</Th>
                <Th>Canal</Th>
                <Th>Destino</Th>
                <Th>Mensaje</Th>
                <Th>Programada</Th>
                <Th>Estado</Th>
                <Th>Intentos</Th>
                <Th className="w-24">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {actions.map(a => {
                const ChannelIcon = channelIcons[a.channel] || Phone
                return (
                  <tr key={a.id} className="hover:bg-bg-hover transition-colors">
                    <Td>
                      <span className="text-sm">
                        {ruleTypeLabels[a.rule_type] || a.rule_type}
                      </span>
                    </Td>
                    <Td>
                      <span className="flex items-center gap-1.5 text-sm">
                        <ChannelIcon size={14} className="text-text-muted" />
                        {channelLabels[a.channel] || a.channel}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-xs">{a.target_number}</span>
                    </Td>
                    <Td>
                      <span className="text-sm text-text-secondary max-w-[200px] truncate block" title={a.message}>
                        {a.message || '—'}
                      </span>
                    </Td>
                    <Td>
                      <span className="flex items-center gap-1 text-xs text-text-muted">
                        <Clock size={12} />
                        {a.scheduled_at
                          ? new Date(a.scheduled_at).toLocaleString('es-MX', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })
                          : '—'}
                      </span>
                    </Td>
                    <Td>
                      <Badge variant={statusBadgeVariant[a.status] || 'default'}>
                        {statusLabels[a.status] || a.status}
                      </Badge>
                    </Td>
                    <Td>
                      <span className="text-xs font-mono">
                        {a.attempts ?? 0}/{a.max_attempts ?? 3}
                      </span>
                    </Td>
                    <Td>
                      <div className="flex items-center gap-1">
                        {a.status === 'pending' && (
                          <button
                            type="button"
                            onClick={() => handleCancel(a)}
                            className="p-1.5 rounded hover:bg-warning/10 text-text-muted hover:text-warning transition-colors cursor-pointer"
                            title="Cancelar"
                          >
                            <XCircle size={14} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDelete(a)}
                          className="p-1.5 rounded hover:bg-red-500/10 text-text-muted hover:text-red-400 transition-colors cursor-pointer"
                          title="Eliminar"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </Td>
                  </tr>
                )
              })}
            </tbody>
          </Table>
        )}
      </Card>

      {/* Modal crear accion */}
      {showCreate && (
        <CreateActionModal
          agentId={selectedAgentId}
          onClose={() => setShowCreate(false)}
          onCreated={action => {
            setActions(prev => [action, ...prev])
            setShowCreate(false)
            toast.success('Accion programada')
          }}
        />
      )}
    </div>
  )
}

function CreateActionModal({ agentId, onClose, onCreated }) {
  const [form, setForm] = useState({
    rule_type: 'custom',
    channel: 'call',
    target_number: '',
    message: '',
    scheduled_at: '',
    max_attempts: 3,
  })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.target_number) return toast.error('Destino requerido')
    if (!form.scheduled_at) return toast.error('Fecha programada requerida')
    setSaving(true)
    try {
      const body = {
        ...form,
        max_attempts: Number(form.max_attempts),
        scheduled_at: new Date(form.scheduled_at).toISOString(),
      }
      const created = await api.post(`/proactive/agents/${agentId}/scheduled-actions`, body)
      onCreated(created)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const set = (key, value) => setForm(f => ({ ...f, [key]: value }))

  return (
    <Modal open={true} title="Nueva accion proactiva" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Tipo */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Tipo de regla</label>
          <select
            value={form.rule_type}
            onChange={e => set('rule_type', e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
          >
            {RULE_TYPE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Canal */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Canal</label>
          <select
            value={form.channel}
            onChange={e => set('channel', e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
          >
            {CHANNEL_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Destino */}
        <Input
          label="Destino (telefono) *"
          value={form.target_number}
          onChange={e => set('target_number', e.target.value)}
          placeholder="+521XXXXXXXXXX"
          required
        />

        {/* Mensaje */}
        <div>
          <label className="block text-xs text-text-muted mb-1">Mensaje</label>
          <textarea
            value={form.message}
            onChange={e => set('message', e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm resize-y min-h-[80px] focus:outline-none focus:border-accent"
            rows={3}
            placeholder="Mensaje o instrucciones para la accion..."
          />
        </div>

        {/* Fecha programada */}
        <Input
          label="Fecha y hora programada *"
          type="datetime-local"
          value={form.scheduled_at}
          onChange={e => set('scheduled_at', e.target.value)}
          required
        />

        {/* Max intentos */}
        <Input
          label="Intentos maximos"
          type="number"
          min={1}
          max={10}
          value={form.max_attempts}
          onChange={e => set('max_attempts', e.target.value)}
        />

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>
            {saving ? 'Programando...' : 'Programar'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
