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
  Globe, Check, AlertCircle, Edit2, X,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const METHOD_COLORS = {
  GET: 'bg-emerald-500/20 text-emerald-400',
  POST: 'bg-blue-500/20 text-blue-400',
  PUT: 'bg-amber-500/20 text-amber-400',
  PATCH: 'bg-orange-500/20 text-orange-400',
  DELETE: 'bg-red-500/20 text-red-400',
}

const EMPTY_FORM = {
  name: '',
  description: '',
  url: '',
  method: 'POST',
  headers: {},
  body_template: null,
  query_params: {},
  auth_type: 'none',
  auth_config: {},
  response_type: 'json',
  response_path: '',
  agent_ids: null,
  input_schema: { parameters: [] },
}

export function ApiIntegrations() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
  const clientId = user?.client_id

  const [integrations, setIntegrations] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [testing, setTesting] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [saving, setSaving] = useState(false)

  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [headerKey, setHeaderKey] = useState('')
  const [headerVal, setHeaderVal] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [qpKey, setQpKey] = useState('')
  const [qpVal, setQpVal] = useState('')
  const [agentMode, setAgentMode] = useState('all') // 'all' | 'specific'

  // Param builder
  const [paramName, setParamName] = useState('')
  const [paramType, setParamType] = useState('string')
  const [paramDesc, setParamDesc] = useState('')
  const [paramRequired, setParamRequired] = useState(true)

  useEffect(() => {
    if (!clientId) { setLoading(false); return }
    Promise.all([
      api.get(`/clients/${clientId}/api-integrations`),
      api.get(`/clients/${clientId}/agents`),
    ])
      .then(([i, a]) => { setIntegrations(i); setAgents(a) })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [clientId])

  function openCreate() {
    setEditingId(null)
    setForm({ ...EMPTY_FORM })
    setBodyText('')
    setAgentMode('all')
    setTestResult(null)
    setShowModal(true)
  }

  function openEdit(integ) {
    setEditingId(integ.id)
    setForm({
      name: integ.name,
      description: integ.description || '',
      url: integ.url,
      method: integ.method,
      headers: {},
      body_template: integ.body_template,
      query_params: integ.query_params || {},
      auth_type: integ.auth_type || 'none',
      auth_config: {},
      response_type: integ.response_type || 'json',
      response_path: integ.response_path || '',
      agent_ids: integ.agent_ids,
      input_schema: integ.input_schema || { parameters: [] },
    })
    setBodyText(integ.body_template ? JSON.stringify(integ.body_template, null, 2) : '')
    setAgentMode(integ.agent_ids ? 'specific' : 'all')
    setTestResult(null)
    setShowModal(true)
  }

  async function handleSave() {
    if (!form.name || !form.url) {
      toast.error('Nombre y URL son requeridos')
      return
    }
    setSaving(true)
    try {
      let bodyJson = null
      if (bodyText.trim()) {
        try { bodyJson = JSON.parse(bodyText) }
        catch { toast.error('Body template no es JSON válido'); setSaving(false); return }
      }

      const payload = {
        ...form,
        body_template: bodyJson,
        agent_ids: agentMode === 'all' ? null : (form.agent_ids || []),
      }

      if (editingId) {
        const updated = await api.patch(
          `/clients/${clientId}/api-integrations/${editingId}`, payload
        )
        setIntegrations(prev => prev.map(i => i.id === editingId ? updated : i))
        toast.success('Integración actualizada')
      } else {
        const created = await api.post(`/clients/${clientId}/api-integrations`, payload)
        setIntegrations(prev => [...prev, created])
        toast.success('Integración creada')
      }
      setShowModal(false)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    const ok = await confirm.show('Eliminar integración', '¿Seguro que deseas eliminar esta integración API?')
    if (!ok) return
    try {
      await api.delete(`/clients/${clientId}/api-integrations/${id}`)
      setIntegrations(prev => prev.filter(i => i.id !== id))
      toast.success('Integración eliminada')
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleToggle(integ) {
    try {
      const updated = await api.patch(
        `/clients/${clientId}/api-integrations/${integ.id}`,
        { is_active: !integ.is_active }
      )
      setIntegrations(prev => prev.map(i => i.id === integ.id ? updated : i))
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleTest(id) {
    setTesting(id)
    setTestResult(null)
    try {
      const result = await api.post(`/clients/${clientId}/api-integrations/${id}/test`)
      setTestResult(result)
      if (result.success) {
        // Actualizar last_test_status en la lista
        setIntegrations(prev => prev.map(i =>
          i.id === id ? { ...i, last_test_status: 'success', last_tested_at: new Date().toISOString() } : i
        ))
      }
    } catch (e) {
      setTestResult({ success: false, error: e.message })
    } finally {
      setTesting(null)
    }
  }

  function addHeader() {
    if (!headerKey) return
    setForm(f => ({ ...f, headers: { ...f.headers, [headerKey]: headerVal } }))
    setHeaderKey(''); setHeaderVal('')
  }

  function removeHeader(key) {
    setForm(f => {
      const h = { ...f.headers }; delete h[key]
      return { ...f, headers: h }
    })
  }

  function addQueryParam() {
    if (!qpKey) return
    setForm(f => ({ ...f, query_params: { ...f.query_params, [qpKey]: qpVal } }))
    setQpKey(''); setQpVal('')
  }

  function removeQueryParam(key) {
    setForm(f => {
      const qp = { ...f.query_params }; delete qp[key]
      return { ...f, query_params: qp }
    })
  }

  function addParam() {
    if (!paramName) return
    const newParam = { name: paramName, type: paramType, description: paramDesc, required: paramRequired }
    setForm(f => ({
      ...f,
      input_schema: {
        ...f.input_schema,
        parameters: [...(f.input_schema?.parameters || []), newParam],
      },
    }))
    setParamName(''); setParamType('string'); setParamDesc(''); setParamRequired(true)
  }

  function removeParam(idx) {
    setForm(f => ({
      ...f,
      input_schema: {
        ...f.input_schema,
        parameters: f.input_schema.parameters.filter((_, i) => i !== idx),
      },
    }))
  }

  if (loading) return <PageLoader />

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/integrations" className="text-gray-400 hover:text-white">
            <ChevronLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">API Integrations</h1>
            <p className="text-sm text-gray-400 mt-1">
              Conecta endpoints HTTP como herramientas del agente
            </p>
          </div>
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} className="mr-1" /> Nueva API
        </Button>
      </div>

      {/* List */}
      {integrations.length === 0 ? (
        <Card className="text-center py-12">
          <Globe size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 mb-4">No hay integraciones API configuradas</p>
          <Button onClick={openCreate} variant="secondary">
            <Plus size={16} className="mr-1" /> Crear primera integración
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4">
          {integrations.map(integ => (
            <Card key={integ.id} className={`p-4 ${!integ.is_active ? 'opacity-50' : ''}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${METHOD_COLORS[integ.method] || 'bg-gray-500/20 text-gray-400'}`}>
                      {integ.method}
                    </span>
                    <h3 className="text-white font-semibold truncate">{integ.name}</h3>
                    {integ.last_test_status === 'success' && (
                      <Badge variant="success" size="sm"><Check size={12} className="mr-1" />OK</Badge>
                    )}
                    {integ.last_test_status && integ.last_test_status !== 'success' && (
                      <Badge variant="danger" size="sm"><AlertCircle size={12} className="mr-1" />Error</Badge>
                    )}
                  </div>
                  {integ.description && (
                    <p className="text-sm text-gray-400 mb-1">{integ.description}</p>
                  )}
                  <p className="text-xs text-gray-500 font-mono truncate">{integ.url}</p>
                  {integ.input_schema?.parameters?.length > 0 && (
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {integ.input_schema.parameters.map((p, i) => (
                        <span key={i} className="text-xs bg-white/5 text-gray-400 px-2 py-0.5 rounded">
                          {p.name}{p.required ? '*' : ''}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <Button
                    variant="ghost" size="sm"
                    onClick={() => handleTest(integ.id)}
                    disabled={testing === integ.id}
                  >
                    <TestTube size={14} className={testing === integ.id ? 'animate-pulse' : ''} />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(integ)}>
                    <Edit2 size={14} />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleToggle(integ)}>
                    {integ.is_active
                      ? <Power size={14} className="text-emerald-400" />
                      : <PowerOff size={14} className="text-gray-500" />
                    }
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(integ.id)}>
                    <Trash2 size={14} className="text-red-400" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Test Result Toast (inline) */}
      {testResult && (
        <Card className={`p-4 border ${testResult.success ? 'border-emerald-500/30' : 'border-red-500/30'}`}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                {testResult.success
                  ? <Check size={16} className="text-emerald-400" />
                  : <AlertCircle size={16} className="text-red-400" />
                }
                <span className={`font-semibold ${testResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {testResult.success ? 'Test exitoso' : 'Test fallido'}
                </span>
                {testResult.status_code && (
                  <Badge variant={testResult.success ? 'success' : 'danger'} size="sm">
                    HTTP {testResult.status_code}
                  </Badge>
                )}
              </div>
              {testResult.response_preview && (
                <pre className="text-xs text-gray-400 bg-black/30 rounded p-2 max-h-32 overflow-auto font-mono whitespace-pre-wrap">
                  {testResult.response_preview}
                </pre>
              )}
              {testResult.error && (
                <p className="text-sm text-red-400">{testResult.error}</p>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={() => setTestResult(null)}>
              <X size={14} />
            </Button>
          </div>
        </Card>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title={editingId ? 'Editar integración API' : 'Nueva integración API'}
        size="lg"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
          {/* Name & Description */}
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Nombre *"
              placeholder="consultar_stock"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
            <Input
              label="Descripción"
              placeholder="Consulta stock de productos"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
          </div>

          {/* Method & URL */}
          <div className="grid grid-cols-[120px_1fr] gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Método</label>
              <select
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                value={form.method}
                onChange={e => setForm(f => ({ ...f, method: e.target.value }))}
              >
                {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => (
                  <option key={m} value={m} className="bg-gray-900">{m}</option>
                ))}
              </select>
            </div>
            <Input
              label="URL *"
              placeholder="https://api.example.com/endpoint"
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
            />
          </div>

          {/* Auth */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Autenticación</label>
            <select
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm mb-2"
              value={form.auth_type}
              onChange={e => setForm(f => ({ ...f, auth_type: e.target.value, auth_config: {} }))}
            >
              <option value="none" className="bg-gray-900">Sin autenticación</option>
              <option value="bearer" className="bg-gray-900">Bearer Token</option>
              <option value="api_key" className="bg-gray-900">API Key (header)</option>
              <option value="basic" className="bg-gray-900">Basic Auth</option>
              <option value="custom_header" className="bg-gray-900">Header personalizado</option>
            </select>

            {form.auth_type === 'bearer' && (
              <Input
                label="Token"
                type="password"
                placeholder="tu-token-aqui"
                value={form.auth_config.token || ''}
                onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, token: e.target.value } }))}
              />
            )}
            {form.auth_type === 'api_key' && (
              <div className="grid grid-cols-2 gap-2">
                <Input
                  label="Nombre del header"
                  placeholder="X-API-Key"
                  value={form.auth_config.header_name || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, header_name: e.target.value } }))}
                />
                <Input
                  label="API Key"
                  type="password"
                  placeholder="tu-api-key"
                  value={form.auth_config.api_key || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, api_key: e.target.value } }))}
                />
              </div>
            )}
            {form.auth_type === 'basic' && (
              <div className="grid grid-cols-2 gap-2">
                <Input
                  label="Usuario"
                  value={form.auth_config.username || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, username: e.target.value } }))}
                />
                <Input
                  label="Contraseña"
                  type="password"
                  value={form.auth_config.password || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, password: e.target.value } }))}
                />
              </div>
            )}
            {form.auth_type === 'custom_header' && (
              <div className="grid grid-cols-2 gap-2">
                <Input
                  label="Nombre del header"
                  placeholder="X-Custom-Auth"
                  value={form.auth_config.header_name || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, header_name: e.target.value } }))}
                />
                <Input
                  label="Valor"
                  type="password"
                  value={form.auth_config.header_value || ''}
                  onChange={e => setForm(f => ({ ...f, auth_config: { ...f.auth_config, header_value: e.target.value } }))}
                />
              </div>
            )}
          </div>

          {/* Headers */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Headers adicionales</label>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="Header name"
                value={headerKey}
                onChange={e => setHeaderKey(e.target.value)}
                className="flex-1"
              />
              <Input
                placeholder="Value"
                value={headerVal}
                onChange={e => setHeaderVal(e.target.value)}
                className="flex-1"
              />
              <Button variant="secondary" size="sm" onClick={addHeader}>+</Button>
            </div>
            {Object.entries(form.headers).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                <span className="font-mono">{k}: {v}</span>
                <button onClick={() => removeHeader(k)} className="text-red-400 hover:text-red-300">
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>

          {/* Query Params */}
          {['GET', 'DELETE'].includes(form.method) && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Query Parameters</label>
              <div className="flex gap-2 mb-2">
                <Input placeholder="key" value={qpKey} onChange={e => setQpKey(e.target.value)} className="flex-1" />
                <Input placeholder="value" value={qpVal} onChange={e => setQpVal(e.target.value)} className="flex-1" />
                <Button variant="secondary" size="sm" onClick={addQueryParam}>+</Button>
              </div>
              {Object.entries(form.query_params).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                  <span className="font-mono">{k}={v}</span>
                  <button onClick={() => removeQueryParam(k)} className="text-red-400 hover:text-red-300">
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Body Template */}
          {['POST', 'PUT', 'PATCH'].includes(form.method) && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Body Template (JSON) — usa {'{{variable}}'} para interpolar
              </label>
              <textarea
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm font-mono h-24 resize-y"
                placeholder={'{\n  "product_id": "{{product_id}}",\n  "quantity": "{{quantity}}"\n}'}
                value={bodyText}
                onChange={e => setBodyText(e.target.value)}
              />
            </div>
          )}

          {/* Response */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Tipo de respuesta</label>
              <select
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                value={form.response_type}
                onChange={e => setForm(f => ({ ...f, response_type: e.target.value }))}
              >
                <option value="json" className="bg-gray-900">JSON</option>
                <option value="text" className="bg-gray-900">Texto plano</option>
              </select>
            </div>
            <Input
              label="Response path (dot notation)"
              placeholder="data.result"
              value={form.response_path}
              onChange={e => setForm(f => ({ ...f, response_path: e.target.value }))}
            />
          </div>

          {/* Input Schema (Parameters) */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">
              Parámetros de entrada (los que el agente debe proporcionar)
            </label>
            <div className="flex gap-2 mb-2 items-end">
              <Input
                label="Nombre"
                placeholder="product_id"
                value={paramName}
                onChange={e => setParamName(e.target.value)}
                className="flex-1"
              />
              <div className="flex-1">
                <label className="block text-sm text-gray-400 mb-1">Tipo</label>
                <select
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  value={paramType}
                  onChange={e => setParamType(e.target.value)}
                >
                  <option value="string" className="bg-gray-900">string</option>
                  <option value="number" className="bg-gray-900">number</option>
                  <option value="boolean" className="bg-gray-900">boolean</option>
                </select>
              </div>
              <Input
                label="Descripción"
                placeholder="ID del producto"
                value={paramDesc}
                onChange={e => setParamDesc(e.target.value)}
                className="flex-[2]"
              />
              <label className="flex items-center gap-1 text-xs text-gray-400 pb-2">
                <input
                  type="checkbox"
                  checked={paramRequired}
                  onChange={e => setParamRequired(e.target.checked)}
                  className="accent-cyan-500"
                />
                Req
              </label>
              <Button variant="secondary" size="sm" onClick={addParam} className="mb-0.5">+</Button>
            </div>
            {(form.input_schema?.parameters || []).map((p, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-gray-400 mb-1 bg-white/5 rounded px-2 py-1">
                <span className="font-mono font-semibold text-white">{p.name}</span>
                <Badge size="sm">{p.type}</Badge>
                {p.required && <Badge variant="warning" size="sm">req</Badge>}
                <span className="flex-1 truncate">{p.description}</span>
                <button onClick={() => removeParam(i)} className="text-red-400 hover:text-red-300">
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>

          {/* Agent Assignment */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Asignar a agentes</label>
            <div className="flex gap-4 mb-2">
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="radio" name="agentMode" value="all"
                  checked={agentMode === 'all'}
                  onChange={() => { setAgentMode('all'); setForm(f => ({ ...f, agent_ids: null })) }}
                  className="accent-cyan-500"
                />
                Todos los agentes
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="radio" name="agentMode" value="specific"
                  checked={agentMode === 'specific'}
                  onChange={() => setAgentMode('specific')}
                  className="accent-cyan-500"
                />
                Agentes específicos
              </label>
            </div>
            {agentMode === 'specific' && (
              <div className="space-y-1">
                {agents.map(a => (
                  <label key={a.id} className="flex items-center gap-2 text-sm text-gray-300">
                    <input
                      type="checkbox"
                      checked={(form.agent_ids || []).includes(a.id)}
                      onChange={e => {
                        const ids = new Set(form.agent_ids || [])
                        if (e.target.checked) ids.add(a.id); else ids.delete(a.id)
                        setForm(f => ({ ...f, agent_ids: [...ids] }))
                      }}
                      className="accent-cyan-500"
                    />
                    {a.name}
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Modal footer */}
        <div className="flex justify-between mt-6 pt-4 border-t border-white/10">
          {editingId && (
            <Button
              variant="secondary" size="sm"
              onClick={() => handleTest(editingId)}
              disabled={testing === editingId}
            >
              <TestTube size={14} className={`mr-1 ${testing === editingId ? 'animate-pulse' : ''}`} />
              Probar
            </Button>
          )}
          <div className="flex gap-2 ml-auto">
            <Button variant="ghost" onClick={() => setShowModal(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Guardando...' : editingId ? 'Guardar cambios' : 'Crear integración'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
