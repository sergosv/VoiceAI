import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, ArrowRight } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input, Textarea, Select } from '../components/ui/Input'
import { PageLoader } from '../components/ui/Spinner'

export function Settings() {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [client, setClient] = useState(null)
  const [voices, setVoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (user?.role === 'admin') return setLoading(false)
    if (!user?.client_id) return setLoading(false)
    Promise.all([
      api.get(`/clients/${user.client_id}`),
      api.get('/voices'),
    ]).then(([c, v]) => {
      setClient(c)
      setVoices(v)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [user])

  async function handleSave(e) {
    e.preventDefault()
    if (!client) return
    setSaving(true)
    try {
      const updated = await api.patch(`/clients/${client.id}`, {
        agent_name: client.agent_name,
        greeting: client.greeting,
        system_prompt: client.system_prompt,
        language: client.language,
        max_call_duration_seconds: client.max_call_duration_seconds,
        transfer_number: client.transfer_number || null,
        after_hours_message: client.after_hours_message || null,
      })
      setClient(updated)
      toast.success('Configuración guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />

  // Admin: redirigir a la gestión de clientes
  if (user?.role === 'admin') {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Configuración</h1>
        <Card className="space-y-4">
          <p className="text-text-secondary">
            Como administrador, puedes configurar cada cliente desde la sección de clientes.
          </p>
          <Button onClick={() => navigate('/admin/clients')}>
            <ArrowRight size={16} className="mr-2 inline" /> Ir a Clientes
          </Button>
        </Card>
      </div>
    )
  }

  if (!client) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Configuración</h1>
        <Card><p className="text-text-muted">No se encontró configuración de cliente.</p></Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuración</h1>

      <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Agente de voz</h2>
          <Input
            label="Nombre del agente"
            value={client.agent_name}
            onChange={e => setClient({ ...client, agent_name: e.target.value })}
          />
          <Select
            label="Idioma"
            value={client.language}
            onChange={e => setClient({ ...client, language: e.target.value })}
            options={[
              { value: 'es', label: 'Español' },
              { value: 'en', label: 'English' },
              { value: 'es-en', label: 'Bilingüe' },
            ]}
          />
          <Input
            label="Duración máxima (segundos)"
            type="number"
            value={client.max_call_duration_seconds}
            onChange={e => setClient({ ...client, max_call_duration_seconds: parseInt(e.target.value) || 300 })}
          />
          <Input
            label="Número de transferencia"
            value={client.transfer_number || ''}
            onChange={e => setClient({ ...client, transfer_number: e.target.value })}
            placeholder="+52..."
          />
        </Card>

        <Card className="space-y-4">
          <h2 className="text-sm font-semibold text-text-secondary">Mensajes</h2>
          <Textarea
            label="Saludo"
            value={client.greeting}
            onChange={e => setClient({ ...client, greeting: e.target.value })}
            rows={3}
          />
          <Textarea
            label="System prompt"
            value={client.system_prompt}
            onChange={e => setClient({ ...client, system_prompt: e.target.value })}
            rows={8}
          />
          <Textarea
            label="Mensaje fuera de horario"
            value={client.after_hours_message || ''}
            onChange={e => setClient({ ...client, after_hours_message: e.target.value })}
            rows={2}
          />
        </Card>

        <div className="lg:col-span-2 flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            <Save size={16} className="mr-2 inline" />
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </Button>
        </div>
      </form>
    </div>
  )
}
