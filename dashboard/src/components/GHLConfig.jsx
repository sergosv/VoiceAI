import { useState, useEffect } from 'react'
import {
  Save, Trash2, Check, Copy, Loader2, Zap, ChevronDown, ChevronRight,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'

const GHL_CHANNELS = [
  'WhatsApp', 'SMS', 'Web Chat', 'Facebook', 'Instagram', 'Email', 'Google Business',
]

export function GHLConfig({ clientId, agentId }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [hasConfig, setHasConfig] = useState(false)
  const [hasApiKey, setHasApiKey] = useState(false)
  const [form, setForm] = useState({ ghl_location_id: '', ghl_api_key: '' })

  useEffect(() => {
    loadConfig()
  }, [clientId, agentId])

  async function loadConfig() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp`)
      if (data && data.ghl_location_id) {
        setHasConfig(true)
        setHasApiKey(!!data.has_ghl_api_key)
        setForm({ ghl_location_id: data.ghl_location_id || '', ghl_api_key: '' })
      }
    } catch {
      // No config yet
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!form.ghl_location_id) {
      toast.error('Ingresa el Location ID')
      return
    }
    setSaving(true)
    try {
      const payload = {
        provider: 'gohighlevel',
        ghl_location_id: form.ghl_location_id,
      }
      if (form.ghl_api_key?.trim()) payload.ghl_api_key = form.ghl_api_key.trim()

      // Check if config exists
      try {
        const existing = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp`)
        if (existing) {
          await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
        } else {
          await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
        }
      } catch {
        await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      }

      toast.success('GoHighLevel configurado')
      setHasConfig(true)
      setHasApiKey(true)
    } catch (err) {
      toast.error(err.message || 'Error guardando')
    } finally {
      setSaving(false)
    }
  }

  async function handleDisconnect() {
    const ok = await confirm({
      title: 'Desconectar GoHighLevel',
      message: 'Se eliminara la conexion de GoHighLevel. El agente dejara de responder en esos canales.',
      confirmText: 'Desconectar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, {
        ghl_location_id: null,
        ghl_api_key: null,
        provider: 'evolution',
      })
      setHasConfig(false)
      setHasApiKey(false)
      setForm({ ghl_location_id: '', ghl_api_key: '' })
      toast.success('GoHighLevel desconectado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  const webhookBase = import.meta.env.VITE_API_URL || window.location.origin + '/api'
  // Para el webhook siempre mostrar la URL publica (no localhost)
  const isLocal = webhookBase.includes('localhost') || webhookBase.includes('127.0.0.1')
  const webhookDisplayBase = isLocal
    ? 'https://voiceai-production-f4e4.up.railway.app/api'
    : webhookBase
  const webhookUrl = `${webhookDisplayBase}/webhooks/gohighlevel`

  function copyWebhook() {
    navigator.clipboard.writeText(webhookUrl)
    toast.success('URL copiada')
  }

  if (loading) return <p className="text-sm text-text-muted py-4">Cargando...</p>

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-orange-400" />
          <h2 className="text-sm font-semibold text-text-secondary">GoHighLevel</h2>
          <span className="text-[10px] text-text-muted">Multi-canal</span>
          {hasConfig && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-medium ml-auto flex items-center gap-1">
              <Check size={10} /> Conectado
            </span>
          )}
        </div>

        <p className="text-xs text-text-muted">
          Conecta una subcuenta de GoHighLevel para que tu agente responda automaticamente en todos los canales.
        </p>

        {/* Canales soportados */}
        <div className="flex flex-wrap gap-1.5">
          {GHL_CHANNELS.map(ch => (
            <span key={ch} className="text-[10px] px-2 py-0.5 rounded-full border border-border text-text-muted">
              {ch}
            </span>
          ))}
        </div>

        {/* Config form */}
        <div className="space-y-3 p-3 rounded-lg border border-border bg-bg-primary/50">
          <Input
            label="Location ID (subcuenta)"
            value={form.ghl_location_id}
            onChange={e => setForm(f => ({ ...f, ghl_location_id: e.target.value }))}
            placeholder="ve9EPM428h8vShlRW1KT"
          />
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key / Private Integration Token</label>
            {hasApiKey && !form.ghl_api_key ? (
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

          {/* Webhook URL */}
          <div className="p-3 rounded-lg border border-border bg-bg-secondary/50">
            <label className="block text-xs text-text-muted mb-1">
              Webhook URL (pegar en GHL {'>'} Settings {'>'} Webhooks)
            </label>
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
          </div>

          {/* Instructions */}
          <details className="text-xs text-text-muted">
            <summary className="cursor-pointer hover:text-text-secondary transition-colors">
              Instrucciones de configuracion
            </summary>
            <ol className="mt-2 space-y-1 pl-4 list-decimal">
              <li>En GHL, entra a la <strong>subcuenta</strong> del cliente</li>
              <li>Ve a Settings {'>'} Integrations {'>'} Private Integrations {'>'} Create</li>
              <li>Selecciona scopes: <code>conversations.readonly</code>, <code>conversations.write</code>, <code>contacts.readonly</code></li>
              <li>Copia el <strong>API Key</strong> y pegalo arriba</li>
              <li>Copia el <strong>Location ID</strong> de la URL o de Business Profile</li>
              <li>Ve a Settings {'>'} Webhooks {'>'} agrega la URL de arriba con evento <code>InboundMessage</code></li>
              <li>Guarda aqui y listo</li>
            </ol>
          </details>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={saving} className="flex-1">
            <Save size={14} className="mr-1 inline" />
            {saving ? 'Guardando...' : hasConfig ? 'Actualizar' : 'Conectar'}
          </Button>
          {hasConfig && (
            <Button variant="danger" onClick={handleDisconnect} className="text-xs px-3">
              <Trash2 size={14} />
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
