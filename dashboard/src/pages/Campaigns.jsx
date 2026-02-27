import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { useToast } from '../context/ToastContext'
import { Megaphone, Plus } from 'lucide-react'

const statusColors = {
  draft: 'bg-bg-hover text-text-secondary',
  scheduled: 'bg-accent/20 text-accent',
  running: 'bg-success/20 text-success',
  paused: 'bg-warning/20 text-warning',
  completed: 'bg-purple-500/20 text-purple-400',
}

const statusLabels = {
  draft: 'Borrador',
  scheduled: 'Programada',
  running: 'En ejecución',
  paused: 'Pausada',
  completed: 'Completada',
}

export function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (clientId) params.set('client_id', clientId)
    api.get(`/campaigns?${params}`)
      .then(setCampaigns)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone size={24} /> Campañas
        </h1>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={v => setClientId(v)} />
          <Button onClick={() => setShowCreate(true)}>
            <Plus size={16} className="mr-1" /> Nueva
          </Button>
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : campaigns.length === 0 ? (
        <Card>
          <p className="text-text-muted text-center py-12">
            No hay campañas. Crea una nueva para comenzar a hacer llamadas outbound.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {campaigns.map(c => (
            <Card
              key={c.id}
              className="cursor-pointer hover:border-accent/30 transition-colors"
              onClick={() => navigate(`/campaigns/${c.id}`)}
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold">{c.name}</h3>
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColors[c.status] || ''}`}>
                  {statusLabels[c.status] || c.status}
                </span>
              </div>
              {c.description && (
                <p className="text-xs text-text-secondary mb-3 line-clamp-2">{c.description}</p>
              )}
              {/* Progress */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-text-muted">
                  <span>{c.completed_contacts} / {c.total_contacts} contactos</span>
                  <span>{c.successful_contacts} exitosas</span>
                </div>
                <div className="w-full bg-bg-primary rounded-full h-2">
                  <div
                    className="bg-accent h-2 rounded-full transition-all"
                    style={{
                      width: c.total_contacts > 0
                        ? `${Math.round((c.completed_contacts / c.total_contacts) * 100)}%`
                        : '0%'
                    }}
                  />
                </div>
              </div>
              <p className="text-xs text-text-muted mt-3">
                {c.created_at ? new Date(c.created_at).toLocaleDateString('es-MX') : ''}
              </p>
            </Card>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateCampaignModal
          onClose={() => setShowCreate(false)}
          onCreated={c => {
            setCampaigns(prev => [c, ...prev])
            setShowCreate(false)
            toast.success('Campaña creada')
            navigate(`/campaigns/${c.id}`)
          }}
        />
      )}
    </div>
  )
}

function CreateCampaignModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    script: '',
    max_concurrent: 1,
    retry_attempts: 2,
  })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name || !form.script) return toast.error('Nombre y script requeridos')
    setSaving(true)
    try {
      const created = await api.post('/campaigns', form)
      onCreated(created)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Nueva campaña" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Nombre *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} required />
        <Input label="Descripción" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
        <div>
          <label className="block text-xs text-text-muted mb-1">Script del agente (system prompt) *</label>
          <textarea
            value={form.script}
            onChange={e => setForm(f => ({ ...f, script: e.target.value }))}
            className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm resize-y min-h-[100px] focus:outline-none focus:border-accent"
            rows={5}
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Llamadas simultáneas"
            type="number"
            min={1}
            max={5}
            value={form.max_concurrent}
            onChange={e => setForm(f => ({ ...f, max_concurrent: parseInt(e.target.value) || 1 }))}
          />
          <Input
            label="Reintentos"
            type="number"
            min={0}
            max={5}
            value={form.retry_attempts}
            onChange={e => setForm(f => ({ ...f, retry_attempts: parseInt(e.target.value) || 0 }))}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Creando...' : 'Crear'}</Button>
        </div>
      </form>
    </Modal>
  )
}
