import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PageLoader } from '../components/ui/Spinner'
import {
  Calendar, Wrench, Save, TestTube, Check,
  Server, Globe, ChevronRight, Plug,
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
  const [testingCal, setTestingCal] = useState(false)

  const [form, setForm] = useState({
    google_calendar_id: '',
    enabled_tools: ['search_knowledge'],
  })

  const clientId = user?.client_id

  useEffect(() => {
    if (!clientId) {
      setLoading(false)
      return
    }
    api.get(`/clients/${clientId}`)
      .then(c => {
        setClient(c)
        setForm({
          google_calendar_id: c.google_calendar_id || '',
          enabled_tools: c.enabled_tools || ['search_knowledge'],
        })
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await api.patch(`/clients/${clientId}`, form)
      setClient(updated)
      toast.success('Configuracion guardada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
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
  if (!client) return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Plug size={24} /> Integraciones</h1>
      <p className="text-sm text-text-muted">Conecta servicios externos y configura herramientas para tus agentes.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hover:border-accent/30 transition-colors">
          <Link to="/integrations/mcp" className="flex items-center justify-between group">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <Server size={20} className="text-accent" />
              </div>
              <div>
                <h2 className="text-sm font-semibold group-hover:text-accent transition-colors">MCP Servers</h2>
                <p className="text-xs text-text-muted">Herramientas externas via MCP</p>
              </div>
            </div>
            <ChevronRight size={18} className="text-text-muted group-hover:text-accent transition-colors" />
          </Link>
        </Card>
        <Card className="hover:border-accent/30 transition-colors">
          <Link to="/integrations/api" className="flex items-center justify-between group">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                <Globe size={20} className="text-green-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold group-hover:text-accent transition-colors">API Integrations</h2>
                <p className="text-xs text-text-muted">Endpoints HTTP como tools</p>
              </div>
            </div>
            <ChevronRight size={18} className="text-text-muted group-hover:text-accent transition-colors" />
          </Link>
        </Card>
      </div>
    </div>
  )

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

      </div>

      {/* MCP y API links */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hover:border-accent/30 transition-colors">
          <Link to="/integrations/mcp" className="flex items-center justify-between group">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <Server size={20} className="text-accent" />
              </div>
              <div>
                <h2 className="text-sm font-semibold group-hover:text-accent transition-colors">MCP Servers</h2>
                <p className="text-xs text-text-muted">Herramientas externas via MCP</p>
              </div>
            </div>
            <ChevronRight size={18} className="text-text-muted group-hover:text-accent transition-colors" />
          </Link>
        </Card>
        <Card className="hover:border-accent/30 transition-colors">
          <Link to="/integrations/api" className="flex items-center justify-between group">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                <Globe size={20} className="text-green-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold group-hover:text-accent transition-colors">API Integrations</h2>
                <p className="text-xs text-text-muted">Endpoints HTTP como tools</p>
              </div>
            </div>
            <ChevronRight size={18} className="text-text-muted group-hover:text-accent transition-colors" />
          </Link>
        </Card>
      </div>

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
