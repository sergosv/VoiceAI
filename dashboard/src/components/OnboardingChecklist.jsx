import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Check, Bot, FileText, Phone, TestTube, X, ChevronDown, ChevronUp,
  CreditCard, Volume2, Sparkles,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const STEPS = [
  {
    key: 'create_agent',
    label: 'Crea tu primer agente',
    desc: 'Dale nombre y personalidad a tu agente de IA.',
    icon: Bot,
    path: '/settings',
  },
  {
    key: 'configure_voice',
    label: 'Configura la voz',
    desc: 'Elige la voz y estilo de tu agente.',
    icon: Volume2,
    path: '/settings',
  },
  {
    key: 'upload_docs',
    label: 'Sube documentos',
    desc: 'Agrega tu base de conocimientos para respuestas precisas.',
    icon: FileText,
    path: '/documents',
  },
  {
    key: 'test_call',
    label: 'Haz una llamada de prueba',
    desc: 'Verifica que tu agente responda correctamente.',
    icon: TestTube,
    path: '/settings',
  },
  {
    key: 'add_credits',
    label: 'Agrega creditos',
    desc: 'Carga saldo para activar llamadas en produccion.',
    icon: CreditCard,
    path: '/billing',
  },
]

export function OnboardingChecklist() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [progress, setProgress] = useState({})
  const [completed, setCompleted] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [showCelebration, setShowCelebration] = useState(false)

  const clientId = user?.client_id

  // Auto-detectar pasos completados a partir de datos existentes
  const autoDetect = useCallback(async (currentProgress) => {
    if (!clientId) return currentProgress
    const updated = { ...currentProgress }
    let changed = false

    try {
      const [agents, docs, calls, billing] = await Promise.all([
        api.get(`/clients/${clientId}/agents`).catch(() => []),
        api.get('/documents?per_page=1').catch(() => []),
        api.get('/calls?per_page=1').catch(() => []),
        api.get('/billing/balance').catch(() => null),
      ])

      // Crea tu primer agente
      if (!updated.create_agent && Array.isArray(agents) && agents.length > 0) {
        updated.create_agent = true
        changed = true
      }

      // Configura la voz
      if (!updated.configure_voice && Array.isArray(agents) && agents.some(a => a.tts_voice)) {
        updated.configure_voice = true
        changed = true
      }

      // Sube documentos
      if (!updated.upload_docs && Array.isArray(docs) && docs.length > 0) {
        updated.upload_docs = true
        changed = true
      }

      // Haz una llamada de prueba
      if (!updated.test_call && Array.isArray(calls) && calls.length > 0) {
        updated.test_call = true
        changed = true
      }

      // Agrega creditos
      if (!updated.add_credits && billing && (billing.balance > 0 || billing.credits > 0)) {
        updated.add_credits = true
        changed = true
      }
    } catch {
      // No falla si la deteccion automatica tiene problemas
    }

    // Persistir cambios detectados automaticamente
    if (changed) {
      const stepsToSync = STEPS.filter(s => updated[s.key] && !currentProgress[s.key])
      for (const step of stepsToSync) {
        try {
          await api.patch('/dashboard/onboarding', { step: step.key })
        } catch {
          // Silenciar errores de sync
        }
      }
    }

    return updated
  }, [clientId])

  useEffect(() => {
    if (!clientId || user?.role === 'admin') return

    let cancelled = false

    async function load() {
      try {
        // Obtener progreso persistido del servidor
        const res = await api.get('/dashboard/onboarding')
        if (cancelled) return

        if (res.progress?.dismissed) {
          setDismissed(true)
          setLoaded(true)
          return
        }

        if (res.completed) {
          setCompleted(true)
          setDismissed(true)
          setLoaded(true)
          return
        }

        // Auto-detectar pasos que se completaron fuera del checklist
        const merged = await autoDetect(res.progress || {})
        if (cancelled) return

        setProgress(merged)

        // Verificar si ahora estan todos completos
        const allDone = STEPS.every(s => merged[s.key])
        if (allDone) {
          setCompleted(true)
          setShowCelebration(true)
        }
      } catch {
        // Si falla, mostrar checklist vacio
        setProgress({})
      } finally {
        if (!cancelled) setLoaded(true)
      }
    }

    load()
    return () => { cancelled = true }
  }, [clientId, user?.role, autoDetect])

  // Marcar un paso como completado manualmente
  async function markStep(stepKey) {
    if (progress[stepKey]) return

    const newProgress = { ...progress, [stepKey]: true }
    setProgress(newProgress)

    try {
      const res = await api.patch('/dashboard/onboarding', { step: stepKey })
      if (res.completed) {
        setCompleted(true)
        setShowCelebration(true)
      }
    } catch {
      // Revertir si falla
      setProgress(progress)
    }
  }

  // Dismiss permanente
  async function handleDismiss() {
    setDismissed(true)
    try {
      await api.patch('/dashboard/onboarding', { dismiss: true })
    } catch {
      // OK si falla, ya se oculto localmente
    }
  }

  if (!loaded || dismissed || user?.role === 'admin') return null

  const doneCount = STEPS.filter(s => progress[s.key]).length
  const total = STEPS.length
  const pct = Math.round((doneCount / total) * 100)

  // Celebracion cuando se completan todos
  if (showCelebration) {
    return (
      <div className="bg-gradient-to-r from-accent/15 to-purple-500/15 border border-accent/30 rounded-xl overflow-hidden">
        <div className="px-5 py-6 text-center">
          <div className="flex justify-center mb-3">
            <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center">
              <Sparkles size={24} className="text-accent" />
            </div>
          </div>
          <h3 className="text-lg font-bold mb-1">Tu agente esta listo!</h3>
          <p className="text-sm text-text-muted mb-4">
            Completaste todos los pasos. Tu agente esta configurado y listo para recibir llamadas.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => navigate('/settings')}
              className="px-4 py-2 bg-accent/10 text-accent text-sm rounded-lg hover:bg-accent/20 transition-colors cursor-pointer"
            >
              Ir a mi agente
            </button>
            <button
              onClick={handleDismiss}
              className="px-4 py-2 text-text-muted text-sm rounded-lg hover:bg-bg-hover transition-colors cursor-pointer"
            >
              Ocultar
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-r from-accent/10 to-purple-500/10 border border-accent/20 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between">
        <button
          onClick={() => setCollapsed(c => !c)}
          className="flex items-center gap-3 cursor-pointer"
        >
          <div>
            <h3 className="text-sm font-semibold">Configura tu agente de IA</h3>
            <p className="text-xs text-text-muted mt-0.5">
              {doneCount}/{total} pasos completados
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
          title="Ocultar checklist"
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
            const done = !!progress[step.key]
            const Icon = step.icon
            return (
              <div
                key={step.key}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                  done
                    ? 'bg-success/5 opacity-60'
                    : 'bg-bg-primary/50 hover:bg-bg-hover border border-border/50'
                }`}
              >
                {/* Checkbox / icon */}
                <button
                  onClick={() => !done && markStep(step.key)}
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 cursor-pointer transition-colors ${
                    done ? 'bg-success/20 text-success' : 'bg-accent/10 text-accent hover:bg-accent/20'
                  }`}
                  title={done ? 'Completado' : 'Marcar como completado'}
                >
                  {done ? <Check size={14} /> : <Icon size={14} />}
                </button>

                {/* Text — click navega */}
                <button
                  onClick={() => !done && navigate(step.path)}
                  className="min-w-0 text-left cursor-pointer flex-1"
                >
                  <p className={`text-sm font-medium ${done ? 'line-through text-text-muted' : ''}`}>
                    {step.label}
                  </p>
                  <p className="text-xs text-text-muted truncate">{step.desc}</p>
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
