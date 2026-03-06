import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import {
  Target, Building2, ArrowDownToLine, ArrowUpFromLine, RefreshCw,
  FileText, Workflow, ChevronLeft, ChevronRight, Sparkles, Check, Copy,
  Loader2, ExternalLink,
} from 'lucide-react'
import { Card } from '../components/ui/Card'

const STEPS = ['objective', 'vertical', 'direction', 'template', 'customize', 'result']
const STEP_LABELS = ['Objetivo', 'Industria', 'Direccion', 'Plantilla', 'Personalizar', 'Resultado']

export function AgentWizard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState(0)
  const [objectives, setObjectives] = useState([])
  const [verticals, setVerticals] = useState([])
  const [templates, setTemplates] = useState([])
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)

  // Selecciones
  const [selectedObjective, setSelectedObjective] = useState(null)
  const [selectedVertical, setSelectedVertical] = useState(null)
  const [selectedDirection, setSelectedDirection] = useState(null)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [selectedMode, setSelectedMode] = useState('system_prompt')

  // Config del cliente
  const [config, setConfig] = useState({
    business_name: '',
    agent_name: '',
    tone: '',
    custom_greeting: '',
    transfer_phone: '',
  })

  const [result, setResult] = useState(null)

  // Cargar datos iniciales
  useEffect(() => {
    Promise.all([
      api.get('/templates/objectives'),
      api.get('/templates/verticals'),
    ]).then(([objs, verts]) => {
      setObjectives(objs)
      setVerticals(verts)
    }).catch(console.error)
  }, [])

  // Buscar templates cuando se selecciona vertical + direccion
  useEffect(() => {
    if (selectedVertical && selectedDirection) {
      const params = new URLSearchParams({ vertical: selectedVertical, direction: selectedDirection })
      if (selectedObjective) params.append('objective', selectedObjective)
      api.get(`/templates/search?${params}`).then(setTemplates).catch(console.error)
    }
  }, [selectedVertical, selectedDirection, selectedObjective])

  async function handleGenerate() {
    setGenerating(true)
    try {
      const data = await api.post('/templates/generate', {
        template_id: selectedTemplate.id,
        mode: selectedMode,
        ...config,
      })
      setResult(data)
      setStep(5)
    } catch (err) {
      console.error('Generate error:', err)
    } finally {
      setGenerating(false)
    }
  }

  function handleCopy(text) {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const nextStep = () => setStep(s => Math.min(s + 1, STEPS.length - 1))
  const prevStep = () => setStep(s => Math.max(s - 1, 0))

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Crear Agente</h1>

      {/* Progress bar */}
      <div className="flex items-center mb-8 gap-1">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center flex-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 transition-colors
              ${i < step ? 'bg-accent text-bg-primary' : i === step ? 'bg-accent/20 text-accent border border-accent' : 'bg-bg-secondary text-text-muted border border-border'}`}>
              {i < step ? <Check size={14} /> : i + 1}
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-1 transition-colors ${i < step ? 'bg-accent' : 'bg-border'}`} />
            )}
          </div>
        ))}
      </div>

      {/* ===== PASO 1: OBJETIVO ===== */}
      {step === 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-1">Para que necesitas tu agente?</h2>
          <p className="text-text-muted text-sm mb-6">Selecciona el objetivo principal</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {objectives.map(obj => (
              <button key={obj.slug} onClick={() => { setSelectedObjective(obj.slug); nextStep() }}
                className={`border rounded-xl p-4 text-left transition-all hover:border-accent/50 hover:bg-accent/5
                  ${selectedObjective === obj.slug ? 'border-accent bg-accent/10' : 'border-border bg-bg-secondary'}`}>
                <div className="text-2xl mb-2">{obj.icon}</div>
                <div className="font-semibold text-sm">{obj.name}</div>
                <div className="text-xs text-text-muted mt-1">{obj.description}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ===== PASO 2: VERTICAL ===== */}
      {step === 1 && (
        <div>
          <h2 className="text-lg font-semibold mb-1">Tu industria?</h2>
          <p className="text-text-muted text-sm mb-6">Esto personaliza las preguntas y el vocabulario del agente</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {verticals.map(vert => (
              <button key={vert.slug} onClick={() => { setSelectedVertical(vert.slug); nextStep() }}
                className={`border rounded-xl p-4 text-left transition-all hover:border-accent/50 hover:bg-accent/5
                  ${selectedVertical === vert.slug ? 'border-accent bg-accent/10' : 'border-border bg-bg-secondary'}`}>
                <div className="text-2xl mb-2">{vert.icon}</div>
                <div className="font-semibold text-sm">{vert.name}</div>
                <div className="text-xs text-text-muted mt-1">{vert.description}</div>
              </button>
            ))}
          </div>
          <button onClick={prevStep} className="mt-6 text-text-muted hover:text-text-secondary text-sm flex items-center gap-1">
            <ChevronLeft size={14} /> Atras
          </button>
        </div>
      )}

      {/* ===== PASO 3: DIRECCION ===== */}
      {step === 2 && (
        <div>
          <h2 className="text-lg font-semibold mb-1">Como llegan tus prospectos?</h2>
          <p className="text-text-muted text-sm mb-6">Esto cambia el tono y flujo del agente</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { key: 'inbound', icon: ArrowDownToLine, label: 'Inbound', desc: 'Ellos te llaman o escriben' },
              { key: 'outbound', icon: ArrowUpFromLine, label: 'Outbound', desc: 'Tu los contactas' },
              { key: 'both', icon: RefreshCw, label: 'Ambos', desc: 'Inbound y outbound' },
            ].map(d => (
              <button key={d.key} onClick={() => { setSelectedDirection(d.key); nextStep() }}
                className={`border rounded-xl p-5 text-center transition-all hover:border-accent/50 hover:bg-accent/5
                  ${selectedDirection === d.key ? 'border-accent bg-accent/10' : 'border-border bg-bg-secondary'}`}>
                <d.icon className="mx-auto mb-2 text-accent" size={24} />
                <div className="font-semibold text-sm">{d.label}</div>
                <div className="text-xs text-text-muted mt-1">{d.desc}</div>
              </button>
            ))}
          </div>
          <button onClick={prevStep} className="mt-6 text-text-muted hover:text-text-secondary text-sm flex items-center gap-1">
            <ChevronLeft size={14} /> Atras
          </button>
        </div>
      )}

      {/* ===== PASO 4: SELECCIONAR TEMPLATE + MODO ===== */}
      {step === 3 && (
        <div>
          <h2 className="text-lg font-semibold mb-1">Elige una plantilla</h2>
          <p className="text-text-muted text-sm mb-6">Selecciona la que mejor se ajuste a tu necesidad</p>

          {templates.length === 0 ? (
            <Card className="text-center text-text-muted py-12">
              No hay plantillas para esta combinacion. Prueba otra vertical o direccion.
            </Card>
          ) : (
            <div className="space-y-2 mb-6">
              {templates.map(tpl => (
                <button key={tpl.id} onClick={() => setSelectedTemplate(tpl)}
                  className={`w-full border rounded-xl p-4 text-left transition-all
                    ${selectedTemplate?.id === tpl.id ? 'border-accent bg-accent/10 ring-1 ring-accent/30' : 'border-border bg-bg-secondary hover:border-border-hover'}`}>
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-semibold text-sm">{tpl.name}</div>
                      <div className="text-xs text-text-muted mt-1">{tpl.description}</div>
                    </div>
                    <div className="flex gap-2 shrink-0 ml-3">
                      <span className="text-[10px] bg-bg-primary px-2 py-0.5 rounded border border-border text-text-muted">
                        {tpl.qualification_frameworks?.name || 'Simple'}
                      </span>
                      <span className="text-[10px] bg-bg-primary px-2 py-0.5 rounded border border-border text-text-muted">
                        {tpl.direction}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Seleccion de modo */}
          {selectedTemplate && (
            <div className="mb-6">
              <h3 className="font-semibold text-sm mb-3">Como quieres configurar tu agente?</h3>
              <div className="grid grid-cols-2 gap-3">
                <button onClick={() => setSelectedMode('system_prompt')}
                  className={`border rounded-xl p-4 text-left transition-all
                    ${selectedMode === 'system_prompt' ? 'border-accent bg-accent/10 ring-1 ring-accent/30' : 'border-border bg-bg-secondary hover:border-border-hover'}`}>
                  <FileText className="text-accent mb-2" size={20} />
                  <div className="font-semibold text-sm">System Prompt</div>
                  <div className="text-xs text-text-muted mt-1">
                    Un prompt inteligente que guia toda la conversacion. Mas flexible y natural.
                  </div>
                </button>
                <button onClick={() => setSelectedMode('builder_flow')}
                  className={`border rounded-xl p-4 text-left transition-all
                    ${selectedMode === 'builder_flow' ? 'border-accent bg-accent/10 ring-1 ring-accent/30' : 'border-border bg-bg-secondary hover:border-border-hover'}`}>
                  <Workflow className="text-accent mb-2" size={20} />
                  <div className="font-semibold text-sm">Builder Flow</div>
                  <div className="text-xs text-text-muted mt-1">
                    Flujo visual paso a paso con nodos. Control total de cada etapa.
                  </div>
                </button>
              </div>
            </div>
          )}

          <div className="flex justify-between mt-6">
            <button onClick={prevStep} className="text-text-muted hover:text-text-secondary text-sm flex items-center gap-1">
              <ChevronLeft size={14} /> Atras
            </button>
            {selectedTemplate && (
              <button onClick={nextStep} className="bg-accent text-bg-primary px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-1">
                Siguiente <ChevronRight size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* ===== PASO 5: PERSONALIZAR ===== */}
      {step === 4 && (
        <div>
          <h2 className="text-lg font-semibold mb-1">Personaliza tu agente</h2>
          <p className="text-text-muted text-sm mb-6">Estos datos hacen que el agente suene como parte de tu equipo</p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nombre de tu negocio *</label>
              <input type="text" value={config.business_name}
                onChange={e => setConfig({ ...config, business_name: e.target.value })}
                placeholder="Ej: Inmobiliaria Patria"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Nombre del agente</label>
              <input type="text" value={config.agent_name}
                onChange={e => setConfig({ ...config, agent_name: e.target.value })}
                placeholder="Ej: Sofia, Carlos (o dejalo vacio para 'Asistente')"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tono de comunicacion</label>
              <select value={config.tone}
                onChange={e => setConfig({ ...config, tone: e.target.value })}
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none">
                <option value="">Usar default de la plantilla</option>
                <option value="Profesional y formal">Profesional y formal</option>
                <option value="Profesional pero cercano">Profesional pero cercano</option>
                <option value="Amigable y casual">Amigable y casual</option>
                <option value="Serio y directo">Serio y directo</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Saludo personalizado (opcional)</label>
              <textarea value={config.custom_greeting}
                onChange={e => setConfig({ ...config, custom_greeting: e.target.value })}
                placeholder="Deja vacio para usar el saludo de la plantilla"
                rows={2}
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none resize-none" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Telefono para transferir leads calientes</label>
              <input type="tel" value={config.transfer_phone}
                onChange={e => setConfig({ ...config, transfer_phone: e.target.value })}
                placeholder="+52 999 123 4567"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none" />
            </div>
          </div>

          <div className="flex justify-between mt-8">
            <button onClick={prevStep} className="text-text-muted hover:text-text-secondary text-sm flex items-center gap-1">
              <ChevronLeft size={14} /> Atras
            </button>
            <button onClick={handleGenerate} disabled={!config.business_name || generating}
              className="bg-accent text-bg-primary px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              {generating ? <><Loader2 size={14} className="animate-spin" /> Generando...</> : <><Sparkles size={14} /> Generar mi agente</>}
            </button>
          </div>
        </div>
      )}

      {/* ===== PASO 6: RESULTADO ===== */}
      {step === 5 && result && (
        <div>
          <Card className="bg-accent/10 border-accent/30 mb-6">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
                <Check className="text-accent" size={16} />
              </div>
              <div>
                <div className="text-accent font-semibold text-sm">Agente generado exitosamente</div>
                <div className="text-text-muted text-xs mt-0.5">
                  {result.template_info?.vertical} &bull; {result.template_info?.framework} &bull; {result.template_info?.direction}
                </div>
              </div>
            </div>
          </Card>

          {result.mode === 'system_prompt' ? (
            <div>
              <h3 className="font-semibold text-sm mb-3">Tu System Prompt</h3>
              <div className="bg-bg-secondary border border-border rounded-xl p-5 font-mono text-xs text-text-secondary whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed">
                {result.result}
              </div>
              <div className="flex gap-3 mt-4">
                <button onClick={() => handleCopy(result.result)}
                  className="bg-accent text-bg-primary px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  {copied ? <><Check size={14} /> Copiado</> : <><Copy size={14} /> Copiar prompt</>}
                </button>
                <button onClick={() => navigate('/settings', { state: { generatedPrompt: result.result, agentName: config.agent_name || 'Asistente' } })}
                  className="border border-accent text-accent px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 hover:bg-accent/10">
                  <ExternalLink size={14} /> Crear agente con este prompt
                </button>
              </div>
            </div>
          ) : (
            <div>
              <h3 className="font-semibold text-sm mb-3">Tu Builder Flow</h3>
              <Card className="mb-4">
                <div className="text-xs text-text-muted mb-3">
                  {result.result.nodes?.length || 0} nodos generados
                </div>
                <div className="space-y-1.5">
                  {result.result.nodes?.map((node, i) => (
                    <div key={node.id} className="flex items-center gap-2 py-1">
                      <span className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold text-white shrink-0
                        ${node.type === 'start' ? 'bg-gray-500' :
                          node.type === 'condition' ? 'bg-yellow-500' :
                          node.type === 'action' ? 'bg-purple-500' :
                          node.type === 'transfer' ? 'bg-red-500' :
                          node.type === 'end' ? 'bg-gray-600' : 'bg-blue-500'}`}>
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium">{node.data?.label}</span>
                      <span className="text-[10px] text-text-muted bg-bg-secondary px-1.5 py-0.5 rounded">{node.type}</span>
                    </div>
                  ))}
                </div>
              </Card>
              <button onClick={() => handleCopy(JSON.stringify(result.result, null, 2))}
                className="border border-accent text-accent px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 hover:bg-accent/10">
                <Copy size={14} /> Copiar JSON del flow
              </button>
            </div>
          )}

          <button onClick={() => { setStep(0); setResult(null); setSelectedTemplate(null) }}
            className="mt-8 text-text-muted hover:text-text-secondary text-sm flex items-center gap-1">
            <RefreshCw size={14} /> Crear otro agente
          </button>
        </div>
      )}
    </div>
  )
}
