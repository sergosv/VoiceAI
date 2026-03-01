import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PageLoader } from '../components/ui/Spinner'
import {
  Calendar, MessageCircle, Wrench, Save, TestTube, Check,
  Server, ChevronRight,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const allTools = [
  { key: 'search_knowledge', label: 'Busqueda de conocimientos', desc: 'Consultar base de documentos del negocio' },
  { key: 'schedule_appointment', label: 'Agendar citas', desc: 'El agente puede crear citas durante la llamada' },
  { key: 'send_whatsapp', label: 'Enviar WhatsApp', desc: 'Enviar mensajes de confirmacion por WhatsApp' },
  { key: 'save_contact', label: 'Capturar contactos', desc: 'Guardar datos de contacto del interlocutor' },
]

export function Integrations() {
  const { user } = useAuth()
  const toast = useToast()
  const [client, setClient] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingWa, setTestingWa] = useState(false)
  const [testingCal, setTestingCal] = useState(false)

  const [form, setForm] = useState({
    google_calendar_id: '',
    whatsapp_instance_id: '',
    whatsapp_api_url: '',
    whatsapp_api_key: '',
    enabled_tools: ['search_knowledge'],
  })

  const clientId = user?.client_id

  useEffect(() => {
    if (!clientId) return
    api.get(`/clients/${clientId}`)
      .then(c => {
        setClient(c)
        setForm({
          google_calendar_id: c.google_calendar_id || '',
          whatsapp_instance_id: c.whatsapp_instance_id || '',
          whatsapp_api_url: c.whatsapp_api_url || '',
          whatsapp_api_key: '',
          enabled_tools: c.enabled_tools || ['search_knowledge'],
        })
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  async function handleSave() {
    setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.whatsapp_api_key) delete payload.whatsapp_api_key

      const updated = await api.patch(`/clients/${clientId}`, payload)
      setClient(updated)
      setForm(f => ({ ...f, whatsapp_api_key: '' }))
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTestWhatsApp() {
    setTestingWa(true)
    try {
      const res = await api.post(`/clients/${clientId}/test-whatsapp`)
      toast.success(res.message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTestingWa(false)
    }
  }

  async function handleTestCalendar() {
    setTestingCal(true)
    try {
      const res = await api.post(`/clients/${clientId}/test-calendar`)
      toast.success(res.message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTestingCal(false)
    }
  }

  function toggleTool(key) {
    setForm(f => ({
      ...f,
      enabled_tools: f.enabled_tools.includes(key)
        ? f.enabled_tools.filter(t => t !== key)
        : [...f.enabled_tools, key],
    }))
  }

  if (loading) return <PageLoader />
  if (!client) return <p className="text-text-muted text-center py-12">No tienes un cliente asignado</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Integraciones</h1>
        <Button onClick={handleSave} disabled={saving}>
          <Save size={16} className="mr-1" /> {saving ? 'Guardando...' : 'Guardar todo'}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Google Calendar */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <Calendar size={20} className="text-accent" />
            <h2 className="text-lg font-semibold">Google Calendar</h2>
          </div>
          <p className="text-xs text-text-muted mb-4">
            Conecta tu calendario de Google para que las citas agendadas por el agente
            se sincronicen automaticamente.
          </p>
          <div className="space-y-3">
            <Input
              label="Calendar ID"
              value={form.google_calendar_id}
              onChange={e => setForm(f => ({ ...f, google_calendar_id: e.target.value }))}
              placeholder="usuario@gmail.com o ID del calendario"
            />
            <p className="text-[11px] text-text-muted">
              La Service Account Key se configura desde el panel de admin.
            </p>
            <Button
              variant="secondary"
              onClick={handleTestCalendar}
              disabled={testingCal || !form.google_calendar_id}
              className="text-xs"
            >
              <TestTube size={14} className="mr-1" />
              {testingCal ? 'Probando...' : 'Probar conexion'}
            </Button>
          </div>
        </Card>

        {/* WhatsApp */}
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <MessageCircle size={20} className="text-success" />
            <h2 className="text-lg font-semibold">WhatsApp</h2>
          </div>
          <p className="text-xs text-text-muted mb-4">
            Conecta Evolution API para enviar mensajes de WhatsApp
            (confirmaciones de citas, informacion, etc).
          </p>
          <div className="space-y-3">
            <Input
              label="URL de API"
              value={form.whatsapp_api_url}
              onChange={e => setForm(f => ({ ...f, whatsapp_api_url: e.target.value }))}
              placeholder="https://evo.example.com"
            />
            <Input
              label="Instance ID"
              value={form.whatsapp_instance_id}
              onChange={e => setForm(f => ({ ...f, whatsapp_instance_id: e.target.value }))}
              placeholder="mi-instancia"
            />
            <Input
              label="API Key"
              type="password"
              value={form.whatsapp_api_key}
              onChange={e => setForm(f => ({ ...f, whatsapp_api_key: e.target.value }))}
              placeholder="evo-api-key..."
            />
            <Button
              variant="secondary"
              onClick={handleTestWhatsApp}
              disabled={testingWa || !form.whatsapp_instance_id}
              className="text-xs"
            >
              <TestTube size={14} className="mr-1" />
              {testingWa ? 'Enviando...' : 'Enviar mensaje de prueba'}
            </Button>
          </div>
        </Card>
      </div>

      {/* MCP Servers */}
      <Card>
        <Link to="/integrations/mcp" className="flex items-center justify-between group">
          <div className="flex items-center gap-3">
            <Server size={20} className="text-accent" />
            <div>
              <h2 className="text-lg font-semibold group-hover:text-accent transition-colors">
                MCP Servers
              </h2>
              <p className="text-xs text-text-muted">
                Conecta herramientas externas (CRMs, hojas de calculo, APIs)
                via Model Context Protocol para que tus agentes las usen en llamadas.
              </p>
            </div>
          </div>
          <ChevronRight size={20} className="text-text-muted group-hover:text-accent transition-colors" />
        </Link>
      </Card>

      {/* Herramientas del agente */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Wrench size={20} className="text-warning" />
          <h2 className="text-lg font-semibold">Herramientas del agente</h2>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Selecciona que herramientas puede usar el agente de voz durante las llamadas.
        </p>
        <div className="space-y-3">
          {allTools.map(tool => {
            const enabled = form.enabled_tools.includes(tool.key)
            return (
              <label
                key={tool.key}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  enabled
                    ? 'border-accent/30 bg-accent/5'
                    : 'border-border bg-bg-primary hover:bg-bg-hover'
                }`}
              >
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => toggleTool(tool.key)}
                  className="sr-only"
                />
                <div className={`w-5 h-5 rounded flex items-center justify-center ${
                  enabled ? 'bg-accent text-black' : 'bg-bg-hover border border-border'
                }`}>
                  {enabled && <Check size={12} />}
                </div>
                <div>
                  <p className="text-sm font-medium">{tool.label}</p>
                  <p className="text-xs text-text-muted">{tool.desc}</p>
                </div>
              </label>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
