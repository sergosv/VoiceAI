import { useState, useEffect } from 'react'
import { Save, Trash2, MessageCircle, Check, Copy } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input, Textarea, Select } from './ui/Input'

export function WhatsAppConfig({ clientId, agentId }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [provider, setProvider] = useState('evolution')
  const [form, setForm] = useState({
    ghl_location_id: '',
    ghl_api_key: '',
    evo_instance_id: '',
    evo_api_url: '',
    evo_api_key: '',
    phone_number: '',
    auto_reply: true,
    greeting: '',
    session_timeout_minutes: 30,
    media_response: 'Solo puedo procesar mensajes de texto por ahora.',
  })

  useEffect(() => {
    loadConfig()
  }, [clientId, agentId])

  async function loadConfig() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp`)
      if (data) {
        setConfig(data)
        setProvider(data.provider)
        setForm({
          ghl_location_id: data.ghl_location_id || '',
          ghl_api_key: '',
          evo_instance_id: data.evo_instance_id || '',
          evo_api_url: data.evo_api_url || '',
          evo_api_key: '',
          phone_number: data.phone_number || '',
          auto_reply: data.auto_reply !== false,
          greeting: data.greeting || '',
          session_timeout_minutes: data.session_timeout_minutes || 30,
          media_response: data.media_response || 'Solo puedo procesar mensajes de texto por ahora.',
        })
      }
    } catch {
      // No config exists yet — that's ok
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        provider,
        phone_number: form.phone_number || null,
        auto_reply: form.auto_reply,
        greeting: form.greeting || null,
        session_timeout_minutes: form.session_timeout_minutes,
        media_response: form.media_response,
      }

      if (provider === 'gohighlevel') {
        payload.ghl_location_id = form.ghl_location_id || null
        if (form.ghl_api_key) payload.ghl_api_key = form.ghl_api_key
      } else {
        payload.evo_instance_id = form.evo_instance_id || null
        payload.evo_api_url = form.evo_api_url || null
        if (form.evo_api_key) payload.evo_api_key = form.evo_api_key
      }

      if (config) {
        await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      } else {
        await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      }
      toast.success('WhatsApp configurado')
      await loadConfig()
    } catch (err) {
      toast.error(err.message || 'Error guardando config')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Eliminar config WhatsApp',
      message: 'Esto desactivará el canal WhatsApp para este agente.',
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/clients/${clientId}/agents/${agentId}/whatsapp`)
      setConfig(null)
      toast.success('Config WhatsApp eliminada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const webhookBase = window.location.origin + '/api/webhooks/whatsapp'
  const webhookUrl = provider === 'gohighlevel'
    ? `${webhookBase}/gohighlevel`
    : `${webhookBase}/evolution`

  function copyWebhook() {
    navigator.clipboard.writeText(webhookUrl)
    toast.success('URL copiada')
  }

  if (loading) return <p className="text-sm text-text-muted py-4">Cargando...</p>

  return (
    <Card className="space-y-4">
      <div className="flex items-center gap-2">
        <MessageCircle size={18} className="text-green-400" />
        <h2 className="text-sm font-semibold text-text-secondary">Canal WhatsApp</h2>
        {config && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 font-medium ml-auto">
            Configurado
          </span>
        )}
      </div>

      {/* Provider tabs */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setProvider('evolution')}
          className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${
            provider === 'evolution'
              ? 'border-green-400 bg-green-400/10 text-green-400'
              : 'border-border text-text-muted hover:border-text-muted'
          }`}
        >
          Evolution API
        </button>
        <button
          type="button"
          onClick={() => setProvider('gohighlevel')}
          className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${
            provider === 'gohighlevel'
              ? 'border-green-400 bg-green-400/10 text-green-400'
              : 'border-border text-text-muted hover:border-text-muted'
          }`}
        >
          GoHighLevel
        </button>
      </div>

      {/* Provider-specific fields */}
      {provider === 'evolution' ? (
        <div className="space-y-3 p-3 rounded-lg border border-border bg-bg-primary/50">
          <Input
            label="Instance ID"
            value={form.evo_instance_id}
            onChange={e => setForm(f => ({ ...f, evo_instance_id: e.target.value }))}
            placeholder="mi-instancia"
          />
          <Input
            label="API URL"
            value={form.evo_api_url}
            onChange={e => setForm(f => ({ ...f, evo_api_url: e.target.value }))}
            placeholder="https://evo.tudominio.com"
          />
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key</label>
            {config?.has_evo_api_key && !form.evo_api_key ? (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-sm flex-1">
                  <Check size={14} className="text-success" />
                  <span className="text-success">Configurada</span>
                </div>
                <Button variant="secondary" onClick={() => setForm(f => ({ ...f, evo_api_key: ' ' }))} className="text-xs px-3">
                  Cambiar
                </Button>
              </div>
            ) : (
              <Input
                type="password"
                value={form.evo_api_key}
                onChange={e => setForm(f => ({ ...f, evo_api_key: e.target.value }))}
                placeholder="B6D711FCDE4D4FD5936544120E7133XX"
              />
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-3 p-3 rounded-lg border border-border bg-bg-primary/50">
          <Input
            label="Location ID"
            value={form.ghl_location_id}
            onChange={e => setForm(f => ({ ...f, ghl_location_id: e.target.value }))}
            placeholder="ve9EPM428h8vShlRW1KT"
          />
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key / Token</label>
            {config?.has_ghl_api_key && !form.ghl_api_key ? (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-sm flex-1">
                  <Check size={14} className="text-success" />
                  <span className="text-success">Configurada</span>
                </div>
                <Button variant="secondary" onClick={() => setForm(f => ({ ...f, ghl_api_key: ' ' }))} className="text-xs px-3">
                  Cambiar
                </Button>
              </div>
            ) : (
              <Input
                type="password"
                value={form.ghl_api_key}
                onChange={e => setForm(f => ({ ...f, ghl_api_key: e.target.value }))}
                placeholder="pit-xxxxxxxx..."
              />
            )}
          </div>
        </div>
      )}

      {/* Webhook URL */}
      <div className="p-3 rounded-lg border border-border bg-bg-primary/50">
        <label className="block text-xs text-text-muted mb-1">Webhook URL</label>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono text-accent bg-bg-secondary px-3 py-2 rounded overflow-x-auto">
            {webhookUrl}
          </code>
          <button
            type="button"
            onClick={copyWebhook}
            className="p-2 text-text-muted hover:text-accent transition-colors"
            title="Copiar"
          >
            <Copy size={14} />
          </button>
        </div>
        <p className="text-[10px] text-text-muted mt-1">
          {provider === 'evolution'
            ? 'Configura esta URL en Evolution API → Settings → Webhook → URL'
            : 'Configura esta URL en GHL → Settings → Webhooks'}
        </p>
      </div>

      {/* Behavior settings */}
      <div className="space-y-3">
        <Input
          label="Numero de WhatsApp"
          value={form.phone_number}
          onChange={e => setForm(f => ({ ...f, phone_number: e.target.value }))}
          placeholder="+5215551234567"
        />

        <Textarea
          label="Saludo inicial (opcional)"
          value={form.greeting}
          onChange={e => setForm(f => ({ ...f, greeting: e.target.value }))}
          rows={2}
          placeholder="Hola! Soy el asistente de [negocio]. ¿En que puedo ayudarte?"
        />

        <Input
          label="Timeout de sesion (minutos)"
          type="number"
          value={form.session_timeout_minutes}
          onChange={e => setForm(f => ({ ...f, session_timeout_minutes: parseInt(e.target.value) || 30 }))}
        />

        <Input
          label="Respuesta a media no soportada"
          value={form.media_response}
          onChange={e => setForm(f => ({ ...f, media_response: e.target.value }))}
        />

        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox"
            checked={form.auto_reply}
            onChange={e => setForm(f => ({ ...f, auto_reply: e.target.checked }))}
            className="accent-green-400"
          />
          Respuesta automatica activada
        </label>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <Button onClick={handleSave} disabled={saving}>
          <Save size={14} className="mr-1 inline" />
          {saving ? 'Guardando...' : config ? 'Actualizar' : 'Activar WhatsApp'}
        </Button>
        {config && (
          <Button variant="danger" onClick={handleDelete}>
            <Trash2 size={14} className="mr-1 inline" /> Eliminar
          </Button>
        )}
      </div>
    </Card>
  )
}
