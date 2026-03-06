import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Bot, FileText, Phone, MessageSquare, TestTube, X, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const STEPS = [
  {
    key: 'agent',
    label: 'Configura tu agente',
    desc: 'Dale nombre, voz y personalidad a tu agente de IA.',
    icon: Bot,
    path: '/settings',
    check: data => data.agents?.length > 0 && data.agents.some(a => a.system_prompt?.length > 20),
  },
  {
    key: 'docs',
    label: 'Sube documentos',
    desc: 'Agrega tu base de conocimientos para que el agente responda con informacion real.',
    icon: FileText,
    path: '/documents',
    check: data => (data.doc_count || 0) > 0,
  },
  {
    key: 'phone',
    label: 'Conecta un telefono',
    desc: 'Asigna un numero telefonico para recibir llamadas.',
    icon: Phone,
    path: '/settings',
    check: data => data.agents?.some(a => a.phone_number),
  },
  {
    key: 'test',
    label: 'Prueba tu agente',
    desc: 'Usa el chat tester para verificar que responde correctamente.',
    icon: TestTube,
    path: '/settings',
    check: data => (data.call_count || 0) > 0 || data.has_tested,
  },
]

export function OnboardingChecklist() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [dismissed, setDismissed] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  const clientId = user?.client_id

  useEffect(() => {
    if (!clientId || user?.role === 'admin') return
    if (localStorage.getItem('onboarding_dismissed') === 'true') {
      setDismissed(true)
      return
    }

    Promise.all([
      api.get(`/clients/${clientId}/agents`).catch(() => []),
      api.get(`/documents?per_page=1`).catch(() => []),
      api.get(`/calls?per_page=1`).catch(() => []),
    ]).then(([agents, docs, calls]) => {
      setData({
        agents,
        doc_count: docs?.length || 0,
        call_count: calls?.length || 0,
        has_tested: false,
      })
    }).catch(() => {})
  }, [clientId])

  if (!data || dismissed || user?.role === 'admin') return null

  const completed = STEPS.filter(s => s.check(data))
  const progress = completed.length
  const total = STEPS.length

  // All done — auto-dismiss
  if (progress === total) {
    if (!localStorage.getItem('onboarding_complete_shown')) {
      localStorage.setItem('onboarding_complete_shown', 'true')
      // Show for one more render then dismiss
    } else {
      return null
    }
  }

  function handleDismiss() {
    localStorage.setItem('onboarding_dismissed', 'true')
    setDismissed(true)
  }

  const pct = Math.round((progress / total) * 100)

  return (
    <div className="bg-gradient-to-r from-accent/10 to-purple-500/10 border border-accent/20 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => setCollapsed(c => !c)}
          className="flex items-center gap-3 cursor-pointer"
        >
          <div>
            <h3 className="text-sm font-semibold">
              {progress === total ? 'Listo! Tu agente esta configurado' : 'Configura tu agente de IA'}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              {progress}/{total} pasos completados
            </p>
          </div>
          {collapsed
            ? <ChevronDown size={16} className="text-text-muted" />
            : <ChevronUp size={16} className="text-text-muted" />
          }
        </button>
        <button
          onClick={handleDismiss}
          className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors cursor-pointer"
          title="Cerrar"
        >
          <X size={14} />
        </button>
      </div>

      {/* Progress bar */}
      <div className="px-5 pb-3">
        <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Steps */}
      {!collapsed && (
        <div className="px-5 pb-4 space-y-1.5">
          {STEPS.map(step => {
            const done = step.check(data)
            const Icon = step.icon
            return (
              <button
                key={step.key}
                onClick={() => !done && navigate(step.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors cursor-pointer ${
                  done
                    ? 'bg-success/5 opacity-60'
                    : 'bg-bg-primary/50 hover:bg-bg-hover border border-border/50'
                }`}
              >
                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                  done ? 'bg-success/20 text-success' : 'bg-accent/10 text-accent'
                }`}>
                  {done ? <Check size={14} /> : <Icon size={14} />}
                </div>
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${done ? 'line-through text-text-muted' : ''}`}>
                    {step.label}
                  </p>
                  <p className="text-xs text-text-muted truncate">{step.desc}</p>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
