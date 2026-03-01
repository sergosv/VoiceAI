import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Badge } from '../components/ui/Badge'
import { PageLoader } from '../components/ui/Spinner'
import {
  Plus, Trash2, TestTube, Power, PowerOff, ChevronLeft,
  Server, Plug, AlertCircle, Check, ExternalLink, Wrench,
} from 'lucide-react'
import { Link } from 'react-router-dom'

// Iconos de Lucide para templates (mapeados por nombre)
import * as LucideIcons from 'lucide-react'

function TemplateIcon({ name, size = 20, className = '' }) {
  const Icon = LucideIcons[name] || Server
  return <Icon size={size} className={className} />
}

export function McpServers() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const clientId = user?.client_id

  const [servers, setServers] = useState([])
  const [templates, setTemplates] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [addTab, setAddTab] = useState('template') // 'template' | 'custom'
  const [testing, setTesting] = useState(null) // server id being tested
  const [testResult, setTestResult] = useState(null)

  const [form, setForm] = useState({
    name: '',
    description: '',
    connection_type: 'http',
    url: '',
    transport_type: 'sse',
    headers: {},
    command: '',
    command_args: [],
    env_vars: {},
    agent_ids: null,
    template_id: null,
  })
  const [envInput, setEnvInput] = useState('') // "KEY=value" format
  const [headerInput, setHeaderInput] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!clientId) return
    Promise.all([
      api.get(`/clients/${clientId}/mcp-servers`),
      api.get('/mcp-templates'),
      api.get(`/clients/${clientId}/agents`),
    ])
      .then(([s, t, a]) => {
        setServers(s)
        setTemplates(t)
        setAgents(a)
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  async function handleCreate() {
    setCreating(true)
    try {
      const payload = { ...form }
      // Parsear env vars de string a dict
      if (envInput.trim()) {
        const env = {}
        envInput.split('\n').forEach(line => {
          const [k, ...v] = line.split('=')
          if (k?.trim()) env[k.trim()] = v.join('=').trim()
        })
        payload.env_vars = env
      }
      // Parsear headers
      if (headerInput.trim()) {
        const headers = {}
        headerInput.split('\n').forEach(line => {
          const [k, ...v] = line.split(':')
          if (k?.trim()) headers[k.trim()] = v.join(':').trim()
        })
        payload.headers = headers
      }
      // command_args de string a array
      if (typeof payload.command_args === 'string') {
        payload.command_args = payload.command_args.split(' ').filter(Boolean)
      }

      const created = await api.post(`/clients/${clientId}/mcp-servers`, payload)
      setServers(prev => [...prev, created])
      setShowAddModal(false)
      resetForm()
      toast.success(`MCP server "${created.name}" creado`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  function resetForm() {
    setForm({
      name: '', description: '', connection_type: 'http', url: '',
      transport_type: 'sse', headers: {}, command: '', command_args: [],
      env_vars: {}, agent_ids: null, template_id: null,
    })
    setEnvInput('')
    setHeaderInput('')
    setAddTab('template')
  }

  function selectTemplate(tmpl) {
    setForm({
      name: tmpl.name,
      description: tmpl.description || '',
      connection_type: tmpl.connection_type,
      url: tmpl.default_url || '',
      transport_type: tmpl.default_transport_type || 'sse',
      headers: {},
      command: tmpl.default_command || '',
      command_args: tmpl.default_command_args || [],
      env_vars: {},
      agent_ids: null,
      template_id: tmpl.id,
    })
    // Pre-fill env var keys
    if (tmpl.required_env_vars?.length) {
      setEnvInput(tmpl.required_env_vars.map(k => `${k}=`).join('\n'))
    }
    setAddTab('custom')
  }

  async function handleToggle(server) {
    try {
      const updated = await api.patch(`/clients/${clientId}/mcp-servers/${server.id}`, {
        is_active: !server.is_active,
      })
      setServers(prev => prev.map(s => s.id === server.id ? updated : s))
      toast.success(updated.is_active ? 'Servidor activado' : 'Servidor desactivado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete(server) {
    const ok = await confirm({
      title: 'Eliminar MCP server',
      message: `Eliminar "${server.name}"? Esta accion no se puede deshacer.`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${clientId}/mcp-servers/${server.id}`)
      setServers(prev => prev.filter(s => s.id !== server.id))
      toast.success('Servidor eliminado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleTest(server) {
    setTesting(server.id)
    setTestResult(null)
    try {
      const result = await api.post(`/clients/${clientId}/mcp-servers/${server.id}/test`)
      setTestResult({ serverId: server.id, ...result })
      if (result.success) {
        // Actualizar tools_cache en estado local
        setServers(prev => prev.map(s =>
          s.id === server.id ? { ...s, tools_cache: result.tools, last_connected_at: new Date().toISOString() } : s
        ))
        toast.success(`${result.tools.length} herramientas descubiertas`)
      } else {
        toast.error(result.error || 'Error de conexion')
      }
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/integrations" className="text-text-muted hover:text-text-primary">
            <ChevronLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">MCP Servers</h1>
            <p className="text-sm text-text-muted">
              Conecta herramientas externas via Model Context Protocol
            </p>
          </div>
        </div>
        <Button onClick={() => { resetForm(); setShowAddModal(true) }}>
          <Plus size={16} className="mr-1" /> Agregar servidor
        </Button>
      </div>

      {/* Lista de servidores */}
      {servers.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <Server size={48} className="mx-auto text-text-muted mb-4 opacity-50" />
            <h3 className="text-lg font-medium mb-2">Sin servidores MCP</h3>
            <p className="text-sm text-text-muted mb-4">
              Agrega un servidor MCP para que tus agentes puedan conectarse a CRMs,
              calendarios, bases de datos y mas.
            </p>
            <Button onClick={() => { resetForm(); setShowAddModal(true) }}>
              <Plus size={16} className="mr-1" /> Agregar primer servidor
            </Button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {servers.map(server => (
            <Card key={server.id}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  {/* Status dot */}
                  <div className={`mt-1 w-3 h-3 rounded-full ${
                    server.is_active ? 'bg-success' : 'bg-text-muted'
                  }`} />
                  <div>
                    <h3 className="font-semibold">{server.name}</h3>
                    {server.description && (
                      <p className="text-sm text-text-muted mt-0.5">{server.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
                      <Badge variant={server.connection_type === 'http' ? 'inbound' : 'outbound'}>
                        {server.connection_type === 'http' ? `HTTP/${server.transport_type}` : 'stdio'}
                      </Badge>
                      {server.tools_cache && (
                        <span className="flex items-center gap-1">
                          <Wrench size={12} />
                          {server.tools_cache.length} herramientas
                        </span>
                      )}
                      {server.agent_ids ? (
                        <span>{server.agent_ids.length} agente(s) asignados</span>
                      ) : (
                        <span>Todos los agentes</span>
                      )}
                      {server.last_connected_at && (
                        <span>
                          Probado: {new Date(server.last_connected_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>

                    {/* Tool list expandida si hay test result para este server */}
                    {testResult?.serverId === server.id && testResult.success && (
                      <div className="mt-3 p-3 bg-bg-primary rounded-lg border border-border">
                        <p className="text-xs font-medium text-text-secondary mb-2">
                          Herramientas descubiertas:
                        </p>
                        <div className="space-y-1">
                          {testResult.tools.map((tool, i) => (
                            <div key={i} className="text-xs">
                              <span className="font-mono text-accent">{tool.name}</span>
                              {tool.description && (
                                <span className="text-text-muted ml-2">
                                  {tool.description.slice(0, 100)}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {testResult?.serverId === server.id && !testResult.success && (
                      <div className="mt-3 p-3 bg-danger/10 rounded-lg border border-danger/20">
                        <p className="text-xs text-danger flex items-center gap-1">
                          <AlertCircle size={12} />
                          {testResult.error}
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Acciones */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => handleTest(server)}
                    disabled={testing === server.id}
                    className="text-xs"
                  >
                    <TestTube size={14} className="mr-1" />
                    {testing === server.id ? 'Probando...' : 'Probar'}
                  </Button>
                  <button
                    onClick={() => handleToggle(server)}
                    className={`p-2 rounded-lg transition-colors cursor-pointer ${
                      server.is_active
                        ? 'text-success hover:bg-success/10'
                        : 'text-text-muted hover:bg-bg-hover'
                    }`}
                    title={server.is_active ? 'Desactivar' : 'Activar'}
                  >
                    {server.is_active ? <Power size={16} /> : <PowerOff size={16} />}
                  </button>
                  <button
                    onClick={() => handleDelete(server)}
                    className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                    title="Eliminar"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Agregar servidor */}
      <Modal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Agregar MCP Server"
        maxWidth="max-w-2xl"
      >
        {/* Tabs */}
        <div className="flex gap-1 mb-4 p-1 bg-bg-primary rounded-lg">
          <button
            onClick={() => setAddTab('template')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors cursor-pointer ${
              addTab === 'template'
                ? 'bg-accent/20 text-accent'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Templates
          </button>
          <button
            onClick={() => setAddTab('custom')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors cursor-pointer ${
              addTab === 'custom'
                ? 'bg-accent/20 text-accent'
                : 'text-text-muted hover:text-text-primary'
            }`}
          >
            Personalizado
          </button>
        </div>

        {addTab === 'template' ? (
          /* Template gallery */
          <div className="grid grid-cols-2 gap-3">
            {templates.map(tmpl => (
              <button
                key={tmpl.id}
                onClick={() => selectTemplate(tmpl)}
                className="text-left p-4 rounded-lg border border-border bg-bg-primary hover:bg-bg-hover hover:border-accent/30 transition-all cursor-pointer"
              >
                <div className="flex items-center gap-2 mb-2">
                  <TemplateIcon name={tmpl.icon} size={20} className="text-accent" />
                  <span className="font-medium text-sm">{tmpl.name}</span>
                </div>
                <p className="text-xs text-text-muted line-clamp-2">{tmpl.description}</p>
                {tmpl.required_env_vars?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {tmpl.required_env_vars.map(v => (
                      <span key={v} className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning font-mono">
                        {v}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        ) : (
          /* Custom form */
          <div className="space-y-4">
            <Input
              label="Nombre"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Mi CRM Server"
            />
            <Input
              label="Descripcion"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Conecta con el CRM para leer contactos..."
            />

            {/* Connection type */}
            <div>
              <label className="text-sm text-text-secondary mb-1 block">Tipo de conexion</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setForm(f => ({ ...f, connection_type: 'http' }))}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                    form.connection_type === 'http'
                      ? 'border-accent/30 bg-accent/10 text-accent'
                      : 'border-border text-text-muted hover:bg-bg-hover'
                  }`}
                >
                  <Plug size={14} className="inline mr-1" /> HTTP (SSE)
                </button>
                <button
                  onClick={() => setForm(f => ({ ...f, connection_type: 'stdio' }))}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                    form.connection_type === 'stdio'
                      ? 'border-accent/30 bg-accent/10 text-accent'
                      : 'border-border text-text-muted hover:bg-bg-hover'
                  }`}
                >
                  <Server size={14} className="inline mr-1" /> Stdio
                </button>
              </div>
            </div>

            {form.connection_type === 'http' ? (
              <>
                <Input
                  label="URL del servidor"
                  value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                  placeholder="https://mcp.example.com/sse"
                />
                <div>
                  <label className="text-sm text-text-secondary mb-1 block">Transporte</label>
                  <div className="flex gap-2">
                    {['sse', 'streamable_http'].map(t => (
                      <button
                        key={t}
                        onClick={() => setForm(f => ({ ...f, transport_type: t }))}
                        className={`py-1.5 px-3 rounded-lg border text-xs font-medium transition-colors cursor-pointer ${
                          form.transport_type === t
                            ? 'border-accent/30 bg-accent/10 text-accent'
                            : 'border-border text-text-muted hover:bg-bg-hover'
                        }`}
                      >
                        {t === 'sse' ? 'SSE' : 'Streamable HTTP'}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-sm text-text-secondary mb-1 block">
                    Headers <span className="text-text-muted">(uno por linea: Key: Value)</span>
                  </label>
                  <textarea
                    value={headerInput}
                    onChange={e => setHeaderInput(e.target.value)}
                    placeholder="Authorization: Bearer sk-..."
                    rows={2}
                    className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono placeholder:text-text-muted focus:outline-none focus:border-accent/50"
                  />
                </div>
              </>
            ) : (
              <>
                <Input
                  label="Comando"
                  value={form.command}
                  onChange={e => setForm(f => ({ ...f, command: e.target.value }))}
                  placeholder="npx"
                />
                <Input
                  label="Argumentos (separados por espacio)"
                  value={typeof form.command_args === 'string' ? form.command_args : form.command_args.join(' ')}
                  onChange={e => setForm(f => ({ ...f, command_args: e.target.value }))}
                  placeholder="-y @modelcontextprotocol/server-filesystem /tmp"
                />
              </>
            )}

            {/* Environment variables */}
            <div>
              <label className="text-sm text-text-secondary mb-1 block">
                Variables de entorno <span className="text-text-muted">(KEY=valor, una por linea)</span>
              </label>
              <textarea
                value={envInput}
                onChange={e => setEnvInput(e.target.value)}
                placeholder="API_KEY=sk-abc123&#10;WORKSPACE_ID=ws-456"
                rows={3}
                className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono placeholder:text-text-muted focus:outline-none focus:border-accent/50"
              />
            </div>

            {/* Agent assignment */}
            {agents.length > 1 && (
              <div>
                <label className="text-sm text-text-secondary mb-1 block">Asignar a agentes</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={form.agent_ids === null}
                      onChange={() => setForm(f => ({ ...f, agent_ids: null }))}
                      className="accent-[var(--color-accent)]"
                    />
                    <span className="text-sm">Todos los agentes</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={form.agent_ids !== null}
                      onChange={() => setForm(f => ({ ...f, agent_ids: [] }))}
                      className="accent-[var(--color-accent)]"
                    />
                    <span className="text-sm">Agentes especificos</span>
                  </label>
                  {form.agent_ids !== null && (
                    <div className="pl-6 space-y-1">
                      {agents.map(a => (
                        <label key={a.id} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={form.agent_ids?.includes(a.id)}
                            onChange={e => {
                              setForm(f => ({
                                ...f,
                                agent_ids: e.target.checked
                                  ? [...(f.agent_ids || []), a.id]
                                  : (f.agent_ids || []).filter(id => id !== a.id),
                              }))
                            }}
                            className="accent-[var(--color-accent)]"
                          />
                          <span className="text-sm">{a.name}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setShowAddModal(false)}>
                Cancelar
              </Button>
              <Button onClick={handleCreate} disabled={creating || !form.name}>
                {creating ? 'Creando...' : 'Crear servidor'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
