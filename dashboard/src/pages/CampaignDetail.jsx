import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../context/ToastContext'
import {
  ArrowLeft, Play, Pause, Save, Plus, Trash2, Phone,
  CheckCircle, XCircle, Clock, AlertTriangle,
} from 'lucide-react'

const statusLabels = {
  draft: 'Borrador',
  scheduled: 'Programada',
  running: 'En ejecución',
  paused: 'Pausada',
  completed: 'Completada',
}

const callStatusIcons = {
  pending: <Clock size={14} className="text-text-muted" />,
  calling: <Phone size={14} className="text-accent animate-pulse" />,
  completed: <CheckCircle size={14} className="text-success" />,
  failed: <XCircle size={14} className="text-danger" />,
  no_answer: <AlertTriangle size={14} className="text-warning" />,
  busy: <AlertTriangle size={14} className="text-warning" />,
  retry: <Clock size={14} className="text-warning" />,
}

const callStatusLabels = {
  pending: 'Pendiente',
  calling: 'Llamando',
  completed: 'Completada',
  failed: 'Fallida',
  no_answer: 'Sin respuesta',
  busy: 'Ocupado',
  retry: 'Reintento',
}

export function CampaignDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [campaign, setCampaign] = useState(null)
  const [calls, setCalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showAddContacts, setShowAddContacts] = useState(false)
  const [form, setForm] = useState({})

  useEffect(() => {
    loadData()
  }, [id])

  // Auto-refresh cuando running
  useEffect(() => {
    if (campaign?.status !== 'running') return
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [campaign?.status])

  async function loadData() {
    try {
      const [camp, campCalls] = await Promise.all([
        api.get(`/campaigns/${id}`),
        api.get(`/campaigns/${id}/calls`),
      ])
      setCampaign(camp)
      setCalls(campCalls)
      setForm({
        name: camp.name,
        description: camp.description || '',
        script: camp.script,
        max_concurrent: camp.max_concurrent,
        retry_attempts: camp.retry_attempts,
      })
    } catch (e) {
      toast(e.message, 'error')
      navigate('/campaigns')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await api.patch(`/campaigns/${id}`, form)
      setCampaign(updated)
      toast('Campaña actualizada')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleStart() {
    try {
      const updated = await api.post(`/campaigns/${id}/start`)
      setCampaign(updated)
      toast('Campaña iniciada')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  async function handlePause() {
    try {
      const updated = await api.post(`/campaigns/${id}/pause`)
      setCampaign(updated)
      toast('Campaña pausada')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  async function handleDelete() {
    if (!confirm('¿Eliminar esta campaña?')) return
    try {
      await api.delete(`/campaigns/${id}`)
      toast('Campaña eliminada')
      navigate('/campaigns')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  if (loading) return <PageLoader />
  if (!campaign) return null

  const editable = ['draft', 'paused'].includes(campaign.status)
  const progress = campaign.total_contacts > 0
    ? Math.round((campaign.completed_contacts / campaign.total_contacts) * 100)
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate('/campaigns')}>
            <ArrowLeft size={16} />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{campaign.name}</h1>
            <Badge variant={campaign.status}>{statusLabels[campaign.status]}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {campaign.status === 'running' ? (
            <Button variant="secondary" onClick={handlePause}>
              <Pause size={16} className="mr-1" /> Pausar
            </Button>
          ) : editable && campaign.total_contacts > 0 ? (
            <Button onClick={handleStart}>
              <Play size={16} className="mr-1" /> Iniciar
            </Button>
          ) : null}
          {editable && (
            <Button variant="secondary" className="text-danger" onClick={handleDelete}>
              <Trash2 size={16} />
            </Button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Progreso</span>
          <span className="text-sm text-text-muted">{progress}%</span>
        </div>
        <div className="w-full bg-bg-primary rounded-full h-3">
          <div
            className="bg-accent h-3 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-text-muted">
          <span>{campaign.completed_contacts} / {campaign.total_contacts} completadas</span>
          <span>{campaign.successful_contacts} exitosas</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config */}
        <Card className="lg:col-span-1">
          <h2 className="text-lg font-semibold mb-4">Configuración</h2>
          <div className="space-y-4">
            <Input
              label="Nombre"
              value={form.name || ''}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              disabled={!editable}
            />
            <Input
              label="Descripción"
              value={form.description || ''}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              disabled={!editable}
            />
            <div>
              <label className="block text-xs text-text-muted mb-1">Script del agente</label>
              <textarea
                value={form.script || ''}
                onChange={e => setForm(f => ({ ...f, script: e.target.value }))}
                disabled={!editable}
                className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm resize-y min-h-[100px] focus:outline-none focus:border-accent disabled:opacity-50"
                rows={5}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Simultáneas"
                type="number"
                value={form.max_concurrent || 1}
                onChange={e => setForm(f => ({ ...f, max_concurrent: parseInt(e.target.value) || 1 }))}
                disabled={!editable}
              />
              <Input
                label="Reintentos"
                type="number"
                value={form.retry_attempts || 0}
                onChange={e => setForm(f => ({ ...f, retry_attempts: parseInt(e.target.value) || 0 }))}
                disabled={!editable}
              />
            </div>
            {editable && (
              <Button onClick={handleSave} disabled={saving} className="w-full">
                <Save size={14} className="mr-1" /> {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            )}
          </div>
        </Card>

        {/* Lista de contactos/llamadas */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Contactos ({calls.length})</h2>
            {editable && (
              <Button variant="secondary" onClick={() => setShowAddContacts(true)}>
                <Plus size={16} className="mr-1" /> Agregar
              </Button>
            )}
          </div>
          {calls.length === 0 ? (
            <p className="text-text-muted text-center py-8">
              Sin contactos. Agrega contactos para iniciar la campaña.
            </p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Teléfono</Th>
                  <Th>Estado</Th>
                  <Th>Intento</Th>
                  <Th>Resultado</Th>
                </tr>
              </thead>
              <tbody>
                {calls.map(c => (
                  <tr key={c.id}>
                    <Td>
                      <span className="font-mono text-xs">{c.phone}</span>
                    </Td>
                    <Td>
                      <span className="flex items-center gap-1 text-xs">
                        {callStatusIcons[c.status]}
                        {callStatusLabels[c.status] || c.status}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-xs">{c.attempt}</span>
                    </Td>
                    <Td>
                      <span className="text-xs text-text-secondary line-clamp-1">
                        {c.result_summary || '—'}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>

      {showAddContacts && (
        <AddContactsModal
          campaignId={id}
          onClose={() => setShowAddContacts(false)}
          onAdded={() => {
            setShowAddContacts(false)
            loadData()
            toast('Contactos agregados')
          }}
        />
      )}
    </div>
  )
}

function AddContactsModal({ campaignId, onClose, onAdded }) {
  const [phones, setPhones] = useState('')
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    const phoneNumbers = phones
      .split(/[\n,;]+/)
      .map(p => p.trim())
      .filter(Boolean)
    if (!phoneNumbers.length) return toast('Ingresa al menos un número', 'error')
    setSaving(true)
    try {
      await api.post(`/campaigns/${campaignId}/contacts`, { phone_numbers: phoneNumbers })
      onAdded()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Agregar contactos" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-text-muted mb-1">
            Números de teléfono (uno por línea, o separados por comas)
          </label>
          <textarea
            value={phones}
            onChange={e => setPhones(e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm font-mono resize-y min-h-[120px] focus:outline-none focus:border-accent"
            rows={6}
            placeholder={"+5215512345678\n+5215587654321"}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Agregando...' : 'Agregar'}</Button>
        </div>
      </form>
    </Modal>
  )
}
