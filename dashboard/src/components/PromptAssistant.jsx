import { useState } from 'react'
import { Sparkles, Wand2, RefreshCw, Check, X } from 'lucide-react'
import { api } from '../lib/api'
import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { Input, Select } from './ui/Input'
import { Spinner } from './ui/Spinner'

const TONES = [
  { value: 'profesional', label: 'Profesional' },
  { value: 'amigable', label: 'Amigable y cercano' },
  { value: 'formal', label: 'Formal y serio' },
  { value: 'casual', label: 'Casual y relajado' },
  { value: 'empatico', label: 'Empatico y comprensivo' },
]

const FUNCTIONS = [
  { value: 'atencion_general', label: 'Atencion general' },
  { value: 'agendar_citas', label: 'Agendar citas' },
  { value: 'soporte_tecnico', label: 'Soporte tecnico' },
  { value: 'ventas', label: 'Ventas' },
  { value: 'informacion', label: 'Dar informacion' },
  { value: 'recados', label: 'Tomar recados' },
]

const OBJECTIVES = [
  { value: 'agendar_demo', label: 'Agendar demo/cita' },
  { value: 'venta_directa', label: 'Venta directa' },
  { value: 'encuesta', label: 'Encuesta/feedback' },
  { value: 'seguimiento', label: 'Seguimiento de lead' },
  { value: 'cobranza', label: 'Cobranza' },
  { value: 'recordatorio', label: 'Recordatorio' },
]

const OBJECTION_STYLES = [
  { value: 'empatico', label: 'Empatico — escuchar y validar' },
  { value: 'persistente', label: 'Persistente — insistir con tacto' },
  { value: 'informativo', label: 'Informativo — datos y beneficios' },
  { value: 'respetuoso', label: 'Respetuoso — aceptar y cerrar' },
]

export function PromptAssistant({
  type = 'agent',
  currentPrompt = '',
  onApply,
  agentName = '',
  businessName = '',
}) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState(currentPrompt ? 'improve' : 'create')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')

  // Campos para agente
  const [agentForm, setAgentForm] = useState({
    business_name: businessName,
    business_type: '',
    agent_name: agentName,
    tone: 'profesional',
    main_function: 'atencion_general',
  })

  // Campos para campana
  const [campaignForm, setCampaignForm] = useState({
    objective: 'agendar_demo',
    product: '',
    hook: '',
    data_to_capture: '',
    objection_handling: 'empatico',
  })

  function handleOpen() {
    setMode(currentPrompt ? 'improve' : 'create')
    setResult('')
    setAgentForm(f => ({
      ...f,
      business_name: businessName || f.business_name,
      agent_name: agentName || f.agent_name,
    }))
    setOpen(true)
  }

  async function handleGenerate() {
    setLoading(true)
    setResult('')
    try {
      const body = type === 'campaign'
        ? { type: 'campaign', business_name: businessName, agent_name: agentName, ...campaignForm }
        : { type: 'agent', ...agentForm }
      const data = await api.post('/ai/generate-prompt', body)
      setResult(data.prompt)
    } catch (err) {
      setResult(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleImprove() {
    setLoading(true)
    setResult('')
    try {
      const data = await api.post('/ai/improve-prompt', { prompt: currentPrompt, type })
      setResult(data.prompt)
    } catch (err) {
      setResult(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  function handleApply() {
    if (result && !result.startsWith('Error:')) {
      onApply(result)
      setOpen(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg
          bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20
          transition-colors cursor-pointer"
      >
        <Sparkles size={14} />
        Asistente IA
      </button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Asistente IA para prompts"
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4">
          {/* Selector de modo */}
          {!result && (
            <>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setMode('create')}
                  className={`flex-1 py-2 px-3 text-sm rounded-lg border transition-colors cursor-pointer ${
                    mode === 'create'
                      ? 'bg-accent/10 border-accent text-accent'
                      : 'border-border text-text-muted hover:border-text-secondary'
                  }`}
                >
                  <Sparkles size={14} className="inline mr-1.5 -mt-0.5" />
                  Crear desde cero
                </button>
                <button
                  type="button"
                  onClick={() => setMode('improve')}
                  disabled={!currentPrompt}
                  className={`flex-1 py-2 px-3 text-sm rounded-lg border transition-colors cursor-pointer ${
                    mode === 'improve'
                      ? 'bg-accent/10 border-accent text-accent'
                      : 'border-border text-text-muted hover:border-text-secondary'
                  } ${!currentPrompt ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <Wand2 size={14} className="inline mr-1.5 -mt-0.5" />
                  Mejorar prompt actual
                </button>
              </div>

              {/* Formulario crear - agente */}
              {mode === 'create' && type === 'agent' && (
                <div className="space-y-3">
                  <Input
                    label="Nombre del negocio"
                    value={agentForm.business_name}
                    onChange={e => setAgentForm(f => ({ ...f, business_name: e.target.value }))}
                    placeholder="Mi Empresa S.A."
                  />
                  <Input
                    label="Giro del negocio"
                    value={agentForm.business_type}
                    onChange={e => setAgentForm(f => ({ ...f, business_type: e.target.value }))}
                    placeholder="Clinica dental, restaurante, despacho legal..."
                  />
                  <Input
                    label="Nombre del agente"
                    value={agentForm.agent_name}
                    onChange={e => setAgentForm(f => ({ ...f, agent_name: e.target.value }))}
                    placeholder="Maria"
                  />
                  <Select
                    label="Tono"
                    value={agentForm.tone}
                    onChange={e => setAgentForm(f => ({ ...f, tone: e.target.value }))}
                    options={TONES}
                  />
                  <Select
                    label="Funcion principal"
                    value={agentForm.main_function}
                    onChange={e => setAgentForm(f => ({ ...f, main_function: e.target.value }))}
                    options={FUNCTIONS}
                  />
                </div>
              )}

              {/* Formulario crear - campana */}
              {mode === 'create' && type === 'campaign' && (
                <div className="space-y-3">
                  <Select
                    label="Objetivo de la campana"
                    value={campaignForm.objective}
                    onChange={e => setCampaignForm(f => ({ ...f, objective: e.target.value }))}
                    options={OBJECTIVES}
                  />
                  <Input
                    label="Producto o servicio"
                    value={campaignForm.product}
                    onChange={e => setCampaignForm(f => ({ ...f, product: e.target.value }))}
                    placeholder="Software de gestion, seguro de auto..."
                  />
                  <Input
                    label="Gancho o apertura"
                    value={campaignForm.hook}
                    onChange={e => setCampaignForm(f => ({ ...f, hook: e.target.value }))}
                    placeholder="Promocion especial, invitacion a evento..."
                  />
                  <Input
                    label="Datos a capturar"
                    value={campaignForm.data_to_capture}
                    onChange={e => setCampaignForm(f => ({ ...f, data_to_capture: e.target.value }))}
                    placeholder="Email, horario preferido, presupuesto..."
                  />
                  <Select
                    label="Manejo de objeciones"
                    value={campaignForm.objection_handling}
                    onChange={e => setCampaignForm(f => ({ ...f, objection_handling: e.target.value }))}
                    options={OBJECTION_STYLES}
                  />
                </div>
              )}

              {/* Modo mejorar - preview del prompt actual */}
              {mode === 'improve' && currentPrompt && (
                <div>
                  <label className="block text-xs text-text-muted mb-1">Prompt actual</label>
                  <pre className="text-xs bg-bg-hover/50 rounded-lg p-3 whitespace-pre-wrap max-h-40 overflow-y-auto">
                    {currentPrompt}
                  </pre>
                </div>
              )}

              {/* Boton de accion */}
              <Button
                type="button"
                onClick={mode === 'create' ? handleGenerate : handleImprove}
                disabled={loading}
                className="w-full"
              >
                {loading ? (
                  <>
                    <Spinner size={14} className="mr-2 inline" />
                    {mode === 'create' ? 'Generando...' : 'Mejorando...'}
                  </>
                ) : (
                  <>
                    <Sparkles size={14} className="mr-2 inline" />
                    {mode === 'create' ? 'Generar prompt' : 'Mejorar con IA'}
                  </>
                )}
              </Button>
            </>
          )}

          {/* Preview del resultado */}
          {result && (
            <div className="space-y-3">
              <label className="block text-xs text-text-muted">Resultado</label>
              <textarea
                value={result}
                onChange={e => setResult(e.target.value)}
                className="w-full bg-bg-primary border border-border rounded-lg p-3 text-sm
                  resize-y min-h-[200px] max-h-[50vh] focus:outline-none focus:border-accent"
                rows={10}
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  onClick={handleApply}
                  disabled={result.startsWith('Error:')}
                >
                  <Check size={14} className="mr-1.5 inline" />
                  Usar este prompt
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setResult('')
                    mode === 'create' ? handleGenerate() : handleImprove()
                  }}
                  disabled={loading}
                >
                  <RefreshCw size={14} className={`mr-1.5 inline ${loading ? 'animate-spin' : ''}`} />
                  Regenerar
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setResult('')}
                >
                  <X size={14} className="mr-1.5 inline" />
                  Cancelar
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </>
  )
}
