/**
 * Editor visual de lifecycle hooks para agentes.
 * Sección avanzada que permite crear reglas determinísticas
 * por evento y canal.
 */
import { useState, useEffect, useCallback } from 'react'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input, Select, Textarea } from './ui/Input'
import {
  Plus, Trash2, ChevronDown, ChevronRight, GripVertical,
  Phone, MessageCircle, Globe, Zap, Shield, Eye, EyeOff,
  AlertTriangle, CheckCircle, Bell, Code, Filter, Star,
} from 'lucide-react'
import { api } from '../lib/api'

// ── Constantes ──────────────────────────────────────────

const HOOK_EVENTS = [
  { value: 'OnConversationStart', label: 'Al iniciar conversación', group: 'Inicio', icon: '🔵' },
  { value: 'OnGreeting', label: 'En el saludo', group: 'Inicio', icon: '🔵' },
  { value: 'OnUserMessage', label: 'Cuando el usuario habla', group: 'Conversación', icon: '🔴' },
  { value: 'PreResponse', label: 'Antes de responder', group: 'Conversación', icon: '🟢' },
  { value: 'PostResponse', label: 'Después de responder', group: 'Conversación', icon: '🟢' },
  { value: 'PreToolCall', label: 'Antes de ejecutar acción', group: 'Tools', icon: '🟡' },
  { value: 'PostToolCall', label: 'Después de ejecutar acción', group: 'Tools', icon: '🟡' },
  { value: 'OnInactivity', label: 'En silencio/inactividad', group: 'Eventos', icon: '🟣' },
  { value: 'OnSentimentShift', label: 'Cambio de emoción', group: 'Eventos', icon: '🟣' },
  { value: 'OnLanguageSwitch', label: 'Cambio de idioma', group: 'Eventos', icon: '🟣' },
  { value: 'OnGuardrailHit', label: 'Violación de regla', group: 'Eventos', icon: '🟣' },
  { value: 'OnEscalation', label: 'Al escalar/transferir', group: 'Fin', icon: '🔵' },
  { value: 'OnConversationEnd', label: 'Al terminar conversación', group: 'Fin', icon: '🔵' },
  { value: 'PostConversationEnd', label: 'Después de terminar', group: 'Fin', icon: '🔵' },
]

const HOOK_TYPES = [
  { value: 'rule', label: 'Regla (if/then)', icon: Shield, description: 'Condición simple que bloquea o inyecta contexto' },
  { value: 'validate', label: 'Validación', icon: CheckCircle, description: 'Verifica datos requeridos o horario' },
  { value: 'transform', label: 'Transformar', icon: Code, description: 'Modifica el input o output' },
  { value: 'notify', label: 'Notificar', icon: Bell, description: 'Envía notificación sin bloquear' },
  { value: 'prompt', label: 'Prompt (LLM)', icon: AlertTriangle, description: 'Un segundo LLM evalúa si es correcto' },
  { value: 'evaluator', label: 'Evaluador', icon: Eye, description: 'Evalúa y regenera la respuesta si no cumple criterios' },
]

const CHANNELS = [
  { value: '', label: 'Todos los canales' },
  { value: 'voice', label: 'Llamadas', icon: Phone },
  { value: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { value: 'widget', label: 'Widget Web', icon: Globe },
  { value: 'ghl', label: 'GoHighLevel', icon: Zap },
]

const OPERATORS = [
  { value: 'equals', label: 'es igual a' },
  { value: 'not_equals', label: 'no es igual a' },
  { value: 'contains', label: 'contiene' },
  { value: 'not_contains', label: 'no contiene' },
  { value: 'contains_any', label: 'contiene alguno de' },
  { value: 'matches', label: 'coincide con (regex)' },
  { value: 'gt', label: 'mayor que' },
  { value: 'gte', label: 'mayor o igual que' },
  { value: 'lt', label: 'menor que' },
  { value: 'lte', label: 'menor o igual que' },
]

const FIELDS = [
  { value: 'input.text', label: 'Texto del usuario' },
  { value: 'input.day_of_week', label: 'Día de la semana' },
  { value: 'response.text', label: 'Respuesta del agente' },
  { value: 'response.contains_price', label: 'Respuesta contiene precio' },
  { value: 'silence_seconds', label: 'Segundos de silencio' },
  { value: 'inactive_minutes', label: 'Minutos de inactividad' },
  { value: 'sentiment', label: 'Sentimiento detectado' },
  { value: 'tool_name', label: 'Nombre de la tool' },
]

const ACTIONS = [
  { value: 'block', label: 'Bloquear' },
  { value: 'inject_context', label: 'Inyectar contexto al agente' },
  { value: 'speak', label: 'Hacer que el agente diga...' },
  { value: 'close_session', label: 'Cerrar sesión' },
  { value: 'replace_tool', label: 'Reemplazar tool' },
]

const TOOL_MATCHERS = [
  { value: '*', label: 'Cualquier tool' },
  { value: 'schedule_appointment', label: 'Agendar cita' },
  { value: 'transfer_to_human', label: 'Transferir a humano' },
  { value: 'send_whatsapp', label: 'Enviar WhatsApp' },
  { value: 'call_api', label: 'Llamar API' },
  { value: 'save_contact_info', label: 'Guardar contacto' },
  { value: 'search_knowledge', label: 'Buscar conocimiento' },
]

// ── Componente principal ────────────────────────────────

export default function HooksEditor({ clientId, agentId }) {
  const [hooks, setHooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [expandedHook, setExpandedHook] = useState(null)
  const [showNewHook, setShowNewHook] = useState(false)
  const [templates, setTemplates] = useState([])
  const [showTemplates, setShowTemplates] = useState(false)

  // Cargar hooks y templates
  const loadHooks = useCallback(async () => {
    if (!clientId || !agentId) return
    try {
      setLoading(true)
      const [hooksRes, templatesRes] = await Promise.all([
        api.get(`/clients/${clientId}/agents/${agentId}/hooks`),
        api.get(`/clients/hook-templates`),
      ])
      setHooks(hooksRes.data)
      setTemplates(templatesRes.data)
    } catch (err) {
      console.error('Error loading hooks:', err)
    } finally {
      setLoading(false)
    }
  }, [clientId, agentId])

  useEffect(() => { loadHooks() }, [loadHooks])

  // CRUD
  const createHook = async (hookData) => {
    try {
      setSaving(true)
      const res = await api.post(`/clients/${clientId}/agents/${agentId}/hooks`, hookData)
      setHooks(prev => [...prev, res.data])
      setShowNewHook(false)
      setExpandedHook(res.data.id)
    } catch (err) {
      console.error('Error creating hook:', err)
    } finally {
      setSaving(false)
    }
  }

  const updateHook = async (hookId, hookData) => {
    try {
      setSaving(true)
      const res = await api.put(`/clients/${clientId}/agents/${agentId}/hooks/${hookId}`, hookData)
      setHooks(prev => prev.map(h => h.id === hookId ? res.data : h))
    } catch (err) {
      console.error('Error updating hook:', err)
    } finally {
      setSaving(false)
    }
  }

  const deleteHook = async (hookId) => {
    if (!confirm('¿Eliminar esta regla?')) return
    try {
      await api.delete(`/clients/${clientId}/agents/${agentId}/hooks/${hookId}`)
      setHooks(prev => prev.filter(h => h.id !== hookId))
    } catch (err) {
      console.error('Error deleting hook:', err)
    }
  }

  const applyTemplate = async (templateId) => {
    try {
      setSaving(true)
      const res = await api.post(
        `/clients/${clientId}/agents/${agentId}/hooks/from-template?template_id=${templateId}`
      )
      setHooks(prev => [...prev, res.data])
      setShowTemplates(false)
      setExpandedHook(res.data.id)
    } catch (err) {
      console.error('Error applying template:', err)
    } finally {
      setSaving(false)
    }
  }

  const toggleHook = async (hookId) => {
    try {
      const res = await api.put(`/clients/${clientId}/agents/${agentId}/hooks/${hookId}/toggle`)
      setHooks(prev => prev.map(h => h.id === hookId ? res.data : h))
    } catch (err) {
      console.error('Error toggling hook:', err)
    }
  }

  // Agrupar hooks por evento
  const groupedHooks = {}
  for (const hook of hooks) {
    const event = HOOK_EVENTS.find(e => e.value === hook.hook_event)
    const group = event?.group || 'Otro'
    if (!groupedHooks[group]) groupedHooks[group] = []
    groupedHooks[group].push(hook)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        Cargando reglas...
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Reglas de Negocio (Hooks)</h3>
          <p className="text-sm text-gray-400 mt-1">
            Reglas determinísticas que se ejecutan en momentos específicos de la conversación.
            A diferencia del prompt, estas reglas siempre se cumplen al 100%.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setShowTemplates(!showTemplates)}
            className="flex items-center gap-2"
          >
            <Star className="w-4 h-4" />
            Templates
          </Button>
          <Button
            onClick={() => setShowNewHook(true)}
            className="flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Regla Manual
          </Button>
        </div>
      </div>

      {/* Panel de templates */}
      {showTemplates && templates.length > 0 && (
        <Card className="border border-cyan-500/30 bg-[#12121a] p-4">
          <h4 className="text-white font-medium mb-3">Reglas predefinidas — activa con un click</h4>
          <div className="space-y-4">
            {Object.entries(
              templates.reduce((acc, t) => {
                const cat = t.category || 'Otro'
                if (!acc[cat]) acc[cat] = []
                acc[cat].push(t)
                return acc
              }, {})
            ).map(([category, catTemplates]) => (
              <div key={category}>
                <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">{category}</h5>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {catTemplates.map(t => {
                    const alreadyApplied = hooks.some(h => h.name === t.name)
                    return (
                      <button
                        key={t.id}
                        onClick={() => !alreadyApplied && applyTemplate(t.id)}
                        disabled={alreadyApplied || saving}
                        className={`text-left p-3 rounded-lg border transition-colors ${
                          alreadyApplied
                            ? 'border-gray-800 bg-gray-900/30 opacity-50 cursor-not-allowed'
                            : 'border-gray-700/50 bg-[#0a0a0f] hover:border-cyan-500/50 hover:bg-cyan-500/5 cursor-pointer'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-white">{t.name}</span>
                          {alreadyApplied && <CheckCircle className="w-4 h-4 text-green-500" />}
                        </div>
                        <p className="text-xs text-gray-400 mt-1">{t.description}</p>
                        <div className="flex gap-1 mt-2">
                          {t.channel && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{t.channel}</span>
                          )}
                          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{t.hook_type}</span>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Formulario nueva regla */}
      {showNewHook && (
        <Card className="border border-cyan-500/30 bg-[#12121a]">
          <NewHookForm
            onSave={createHook}
            onCancel={() => setShowNewHook(false)}
            saving={saving}
          />
        </Card>
      )}

      {/* Lista de hooks agrupados */}
      {hooks.length === 0 && !showNewHook ? (
        <Card className="bg-[#12121a] border border-gray-700/50 p-8 text-center">
          <Shield className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 mb-2">No hay reglas configuradas</p>
          <p className="text-sm text-gray-500">
            Las reglas permiten controlar exactamente qué puede y no puede hacer tu agente.
            Por ejemplo: no agendar domingos, siempre confirmar nombre antes de agendar, etc.
          </p>
        </Card>
      ) : (
        Object.entries(groupedHooks).map(([group, groupHooks]) => (
          <div key={group} className="space-y-2">
            <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wider px-1">
              {group}
            </h4>
            {groupHooks.map(hook => (
              <HookCard
                key={hook.id}
                hook={hook}
                expanded={expandedHook === hook.id}
                onToggleExpand={() => setExpandedHook(expandedHook === hook.id ? null : hook.id)}
                onUpdate={(data) => updateHook(hook.id, data)}
                onDelete={() => deleteHook(hook.id)}
                onToggle={() => toggleHook(hook.id)}
                saving={saving}
              />
            ))}
          </div>
        ))
      )}
    </div>
  )
}

// ── Formulario nueva regla ──────────────────────────────

function NewHookForm({ onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    hook_event: 'PreToolCall',
    name: '',
    channel: '',
    hook_type: 'rule',
    matcher: '*',
    config: { conditions: [], action: 'block', message: '' },
    priority: 100,
  })

  const handleSave = () => {
    if (!form.name.trim()) return alert('Escribe un nombre para la regla')
    onSave({
      ...form,
      channel: form.channel || null,
    })
  }

  return (
    <div className="p-4 space-y-4">
      <h4 className="text-white font-medium">Nueva Regla</h4>

      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Nombre de la regla"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Ej: No agendar domingos"
        />
        <Select
          label="Evento"
          value={form.hook_event}
          onChange={(e) => setForm({ ...form, hook_event: e.target.value })}
          options={HOOK_EVENTS.map(e => ({ value: e.value, label: `${e.icon} ${e.label}` }))}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Select
          label="Canal"
          value={form.channel}
          onChange={(e) => setForm({ ...form, channel: e.target.value })}
          options={CHANNELS.map(c => ({ value: c.value, label: c.label }))}
        />
        <Select
          label="Tipo"
          value={form.hook_type}
          onChange={(e) => setForm({ ...form, hook_type: e.target.value })}
          options={HOOK_TYPES.map(t => ({ value: t.value, label: t.label }))}
        />
        {(form.hook_event === 'PreToolCall' || form.hook_event === 'PostToolCall') && (
          <Select
            label="Tool"
            value={form.matcher}
            onChange={(e) => setForm({ ...form, matcher: e.target.value })}
            options={TOOL_MATCHERS}
          />
        )}
      </div>

      {/* Config según tipo */}
      <HookConfigEditor
        hookType={form.hook_type}
        config={form.config}
        onChange={(config) => setForm({ ...form, config })}
      />

      <div className="flex justify-end gap-2 pt-2">
        <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? 'Guardando...' : 'Crear Regla'}
        </Button>
      </div>
    </div>
  )
}

// ── Card de hook existente ──────────────────────────────

function HookCard({ hook, expanded, onToggleExpand, onUpdate, onDelete, onToggle, saving }) {
  const event = HOOK_EVENTS.find(e => e.value === hook.hook_event)
  const type = HOOK_TYPES.find(t => t.value === hook.hook_type)
  const channel = CHANNELS.find(c => c.value === (hook.channel || ''))
  const TypeIcon = type?.icon || Shield

  const [editConfig, setEditConfig] = useState(hook.config || {})
  const [editName, setEditName] = useState(hook.name)

  return (
    <Card className={`bg-[#12121a] border ${hook.enabled ? 'border-gray-700/50' : 'border-gray-800/30 opacity-60'}`}>
      {/* Header compacto */}
      <div
        className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/[0.02]"
        onClick={onToggleExpand}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {expanded ? <ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />}
          <span className="text-base">{event?.icon || '⚪'}</span>
          <TypeIcon className="w-4 h-4 text-cyan-400 flex-shrink-0" />
          <span className="text-white font-medium truncate">{hook.name || 'Sin nombre'}</span>
          <span className="text-xs text-gray-500 flex-shrink-0">{event?.label}</span>
          {hook.channel && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 flex-shrink-0">
              {channel?.label || hook.channel}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onToggle}
            className={`p-1 rounded ${hook.enabled ? 'text-cyan-400 hover:text-cyan-300' : 'text-gray-600 hover:text-gray-400'}`}
            title={hook.enabled ? 'Desactivar' : 'Activar'}
          >
            {hook.enabled ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>
          <button
            onClick={onDelete}
            className="p-1 rounded text-gray-600 hover:text-red-400"
            title="Eliminar"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className="border-t border-gray-800 p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Nombre"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
            <Select
              label="Canal"
              value={hook.channel || ''}
              onChange={(e) => onUpdate({ channel: e.target.value || null })}
              options={CHANNELS.map(c => ({ value: c.value, label: c.label }))}
            />
          </div>

          <HookConfigEditor
            hookType={hook.hook_type}
            config={editConfig}
            onChange={setEditConfig}
          />

          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditConfig(hook.config || {})
                setEditName(hook.name)
              }}
            >
              Descartar
            </Button>
            <Button
              size="sm"
              disabled={saving}
              onClick={() => onUpdate({ name: editName, config: editConfig })}
            >
              {saving ? 'Guardando...' : 'Guardar Cambios'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

// ── Editor de config por tipo ───────────────────────────

function HookConfigEditor({ hookType, config, onChange }) {
  const update = (key, value) => onChange({ ...config, [key]: value })

  if (hookType === 'rule') {
    return (
      <div className="space-y-3">
        {/* Condiciones */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">Condiciones (todas deben cumplirse)</label>
          <ConditionsEditor
            conditions={config.conditions || []}
            onChange={(conditions) => update('conditions', conditions)}
          />
        </div>
        {/* Acción */}
        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Acción cuando se cumple"
            value={config.action || 'block'}
            onChange={(e) => update('action', e.target.value)}
            options={ACTIONS}
          />
          <Input
            label={config.action === 'inject_context' ? 'Contexto a inyectar' : 'Mensaje'}
            value={config.message || config.context || ''}
            onChange={(e) => {
              if (config.action === 'inject_context') {
                update('context', e.target.value)
              } else {
                update('message', e.target.value)
              }
            }}
            placeholder={config.action === 'block' ? 'Mensaje que recibe el agente' : 'Texto...'}
          />
        </div>
      </div>
    )
  }

  if (hookType === 'validate') {
    return (
      <div className="space-y-3">
        <Select
          label="Tipo de validación"
          value={config.validate?.check || 'required_fields'}
          onChange={(e) => update('validate', { ...(config.validate || {}), check: e.target.value })}
          options={[
            { value: 'required_fields', label: 'Campos requeridos' },
            { value: 'business_hours', label: 'Horario de negocio' },
          ]}
        />
        {config.validate?.check === 'required_fields' ? (
          <Input
            label="Campos requeridos (separados por coma)"
            value={(config.validate?.required_fields || []).join(', ')}
            onChange={(e) => update('validate', {
              ...(config.validate || {}),
              required_fields: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
            })}
            placeholder="patient_name, date, time"
          />
        ) : (
          <Textarea
            label="Horario (JSON)"
            value={JSON.stringify(config.validate?.hours || { 'mon-fri': '9:00-18:00' }, null, 2)}
            onChange={(e) => {
              try {
                const hours = JSON.parse(e.target.value)
                update('validate', { ...(config.validate || {}), hours })
              } catch { /* ignore parse error while typing */ }
            }}
            rows={3}
          />
        )}
        <Input
          label="Mensaje cuando no valida"
          value={config.validate?.message || config.validate?.outside_hours_message || ''}
          onChange={(e) => update('validate', {
            ...(config.validate || {}),
            message: e.target.value,
            outside_hours_message: e.target.value,
          })}
        />
      </div>
    )
  }

  if (hookType === 'transform') {
    return (
      <div className="space-y-3">
        <Textarea
          label="Transformación (JSON)"
          value={JSON.stringify(config.transform || {}, null, 2)}
          onChange={(e) => {
            try {
              update('transform', JSON.parse(e.target.value))
            } catch { /* ignore */ }
          }}
          rows={3}
          placeholder='{"max_length": 500, "allow_emojis": true}'
        />
        <Input
          label="Texto a agregar al final de la respuesta (opcional)"
          value={config.append || ''}
          onChange={(e) => update('append', e.target.value)}
          placeholder="Los precios pueden variar."
        />
      </div>
    )
  }

  if (hookType === 'notify') {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Canal de notificación"
            value={config.channel || 'webhook'}
            onChange={(e) => update('channel', e.target.value)}
            options={[
              { value: 'webhook', label: 'Webhook' },
              { value: 'whatsapp', label: 'WhatsApp' },
              { value: 'email', label: 'Email' },
            ]}
          />
          <Input
            label={config.channel === 'webhook' ? 'URL del webhook' : 'Destinatario'}
            value={config.url || config.to || ''}
            onChange={(e) => {
              if (config.channel === 'webhook') {
                update('url', e.target.value)
              } else {
                update('to', e.target.value)
              }
            }}
            placeholder={config.channel === 'webhook' ? 'https://...' : 'owner'}
          />
        </div>
        <Input
          label="Plantilla del mensaje"
          value={config.template || ''}
          onChange={(e) => update('template', e.target.value)}
          placeholder="Llamada de {{caller_name}}: {{summary}}"
        />
      </div>
    )
  }

  if (hookType === 'evaluator') {
    return (
      <div className="space-y-3">
        <Textarea
          label="Criterios de evaluación"
          value={config.criteria || ''}
          onChange={(e) => update('criteria', e.target.value)}
          rows={4}
          placeholder="La respuesta NO debe contener diagnósticos médicos, recetas, ni recomendaciones de medicamentos..."
        />
        <Input
          label="Prefijo del feedback (cuando rechaza)"
          value={config.feedback_prefix || 'Corrige tu respuesta:'}
          onChange={(e) => update('feedback_prefix', e.target.value)}
          placeholder="Corrige tu respuesta:"
        />
        <p className="text-xs text-gray-500">
          Un segundo LLM evalúa cada respuesta del agente contra estos criterios.
          Si no pasa, el agente regenera su respuesta automáticamente (solo en texto).
          En voz, inyecta el feedback para la siguiente respuesta.
        </p>
      </div>
    )
  }

  if (hookType === 'prompt') {
    return (
      <div className="space-y-3">
        <Textarea
          label="Pregunta para el LLM evaluador"
          value={config.prompt || ''}
          onChange={(e) => update('prompt', e.target.value)}
          rows={3}
          placeholder="¿Esta respuesta revela información confidencial del negocio?"
        />
        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Si falla la evaluación"
            value={config.on_fail || 'block'}
            onChange={(e) => update('on_fail', e.target.value)}
            options={[
              { value: 'block', label: 'Bloquear' },
              { value: 'inject_context', label: 'Inyectar contexto' },
            ]}
          />
          <Input
            label="Mensaje de bloqueo"
            value={config.message || ''}
            onChange={(e) => update('message', e.target.value)}
            placeholder="No puedo compartir esa información."
          />
        </div>
      </div>
    )
  }

  return null
}

// ── Editor de condiciones ───────────────────────────────

function ConditionsEditor({ conditions, onChange }) {
  const addCondition = () => {
    onChange([...conditions, { field: 'input.text', operator: 'contains', value: '' }])
  }

  const updateCondition = (idx, key, value) => {
    const updated = [...conditions]
    updated[idx] = { ...updated[idx], [key]: value }
    onChange(updated)
  }

  const removeCondition = (idx) => {
    onChange(conditions.filter((_, i) => i !== idx))
  }

  return (
    <div className="space-y-2">
      {conditions.map((cond, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <Select
            value={cond.field}
            onChange={(e) => updateCondition(idx, 'field', e.target.value)}
            options={FIELDS}
            className="flex-1"
          />
          <Select
            value={cond.operator}
            onChange={(e) => updateCondition(idx, 'operator', e.target.value)}
            options={OPERATORS}
            className="flex-1"
          />
          <Input
            value={typeof cond.value === 'object' ? JSON.stringify(cond.value) : (cond.value ?? '')}
            onChange={(e) => {
              let val = e.target.value
              // Intentar parsear arrays para contains_any
              if (cond.operator === 'contains_any' || cond.operator === 'contains_all') {
                try { val = JSON.parse(val) } catch { val = val.split(',').map(s => s.trim()) }
              }
              updateCondition(idx, 'value', val)
            }}
            placeholder="Valor"
            className="flex-1"
          />
          <button
            onClick={() => removeCondition(idx)}
            className="p-1 text-gray-600 hover:text-red-400"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        onClick={addCondition}
        className="text-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
      >
        <Plus className="w-3 h-3" /> Agregar condición
      </button>
    </div>
  )
}
