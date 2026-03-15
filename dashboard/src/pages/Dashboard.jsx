import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Phone, Clock, DollarSign, FileText, MessageCircle, Calendar,
  TrendingUp, Users, CreditCard, ArrowRight, Activity,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { StatsCard } from '../components/StatsCard'
import { UsageChart } from '../components/UsageChart'
import { CallsTable } from '../components/CallsTable'
import { Card } from '../components/ui/Card'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { OnboardingChecklist } from '../components/OnboardingChecklist'

export function Dashboard() {
  const { user, impersonatingClientId } = useAuth()
  const isAdmin = user?.role === 'admin' && !impersonatingClientId
  const toast = useToast()
  const navigate = useNavigate()
  const [overview, setOverview] = useState(null)
  const [usage, setUsage] = useState(null)
  const [recentCalls, setRecentCalls] = useState([])
  const [extra, setExtra] = useState(null)
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const cq = clientId ? `client_id=${clientId}&` : ''
    Promise.all([
      api.get(`/dashboard/overview?${cq}`),
      api.get(`/dashboard/usage?${cq}days=30`),
      api.get(`/calls?${cq}per_page=5`),
      // Extra data para KPIs enriquecidos
      Promise.all([
        api.get(`/analytics/sentiment-distribution?${cq}days=7`).catch(() => []),
        api.get('/whatsapp/stats').catch(() => null),
        api.get('/ghl/stats').catch(() => null),
        api.get(`/analytics/by-agent?${cq}days=7`).catch(() => []),
      ]),
    ]).then(([ov, us, calls, [sentiment, waStats, ghlStats, agents]]) => {
      if (cancelled) return
      setOverview(ov)
      setUsage(us)
      setRecentCalls(calls)
      setExtra({ sentiment, waStats, ghlStats, agents })
    }).catch(err => {
      if (!cancelled) toast.error(err.message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [clientId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <PageLoader />

  // Calcular métricas extra
  const waActive = extra?.waStats?.active_conversations || 0
  const ghlActive = extra?.ghlStats?.active_conversations || 0
  const totalConvs = waActive + ghlActive
  const topAgent = extra?.agents?.[0]
  const sentimentData = Array.isArray(extra?.sentiment) ? extra.sentiment : []
  const positiveSent = sentimentData.find(s => s.sentiment === 'positive')?.count || 0
  const negativeSent = sentimentData.find(s => s.sentiment === 'negative')?.count || 0
  const totalSent = sentimentData.reduce((sum, s) => sum + (s.count || 0), 0)
  const positiveRate = totalSent > 0 ? Math.round((positiveSent / totalSent) * 100) : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Inicio</h1>
          {overview?.client_name && (
            <p className="text-text-secondary text-sm mt-1">{overview.client_name}</p>
          )}
        </div>
        <ClientSelector value={clientId} onChange={setClientId} />
      </div>

      {/* Onboarding */}
      <OnboardingChecklist />

      {/* Row 1: Stats principales */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          icon={Phone}
          label="Llamadas hoy"
          value={overview?.calls_today ?? 0}
          sub={`${overview?.total_calls ?? 0} total`}
        />
        <StatsCard
          icon={Clock}
          label="Minutos hoy"
          value={`${overview?.minutes_today?.toFixed(1) ?? 0}`}
          sub={`${overview?.total_minutes?.toFixed(1) ?? 0} total`}
        />
        <StatsCard
          icon={MessageCircle}
          label="Conversaciones activas"
          value={totalConvs}
          sub={`${waActive} WhatsApp · ${ghlActive} GHL`}
        />
        {isAdmin ? (
          <StatsCard
            icon={DollarSign}
            label="Costo plataforma hoy"
            value={`$${overview?.platform_cost_today?.toFixed(2) ?? '0.00'}`}
            sub={
              overview?.external_cost_today > 0
                ? `+~$${overview.external_cost_today.toFixed(2)} APIs ext.`
                : `$${overview?.platform_cost_total?.toFixed(2) ?? '0.00'} total plataforma`
            }
          />
        ) : (
          <StatsCard
            icon={CreditCard}
            label="Creditos usados hoy"
            value={`${overview?.minutes_today?.toFixed(1) ?? 0}`}
            sub={`${overview?.total_minutes?.toFixed(0) ?? 0} total acumulado`}
          />
        )}
      </div>

      {/* Row 2: Métricas de inteligencia */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Sentimiento 7 días */}
        <Card className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center shrink-0">
            <Activity size={20} className="text-green-400" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-text-muted">Sentimiento (7d)</p>
            {positiveRate !== null ? (
              <>
                <p className="text-lg font-bold text-green-400">{positiveRate}% positivo</p>
                <p className="text-[10px] text-text-muted">
                  {positiveSent} positivos · {negativeSent} negativos de {totalSent}
                </p>
              </>
            ) : (
              <p className="text-sm text-text-muted">Sin datos</p>
            )}
          </div>
        </Card>

        {/* Agente top */}
        <Card className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
            <TrendingUp size={20} className="text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-text-muted">Agente top (7d)</p>
            {topAgent ? (
              <>
                <p className="text-lg font-bold truncate">{topAgent.name}</p>
                <p className="text-[10px] text-text-muted">
                  {topAgent.calls} llamadas · {topAgent.completion_rate?.toFixed(0)}% completadas
                </p>
              </>
            ) : (
              <p className="text-sm text-text-muted">Sin datos</p>
            )}
          </div>
        </Card>

        {/* Documentos */}
        <Card className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center shrink-0">
            <FileText size={20} className="text-purple-400" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-text-muted">Base de conocimientos</p>
            <p className="text-lg font-bold">{overview?.active_documents ?? 0}</p>
            <p className="text-[10px] text-text-muted">documentos activos</p>
          </div>
        </Card>
      </div>

      {/* Chart */}
      <Card>
        <h2 className="text-sm font-semibold text-text-secondary mb-4">Llamadas (30 dias)</h2>
        <UsageChart data={usage?.data} dataKey="calls" label="Llamadas" />
      </Card>

      {/* Recent calls + Quick links */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-secondary">Llamadas recientes</h2>
            <button
              onClick={() => navigate('/calls')}
              className="text-xs text-accent hover:text-accent/80 flex items-center gap-1 cursor-pointer"
            >
              Ver todas <ArrowRight size={12} />
            </button>
          </div>
          <CallsTable calls={recentCalls} />
        </Card>

        {/* Accesos rápidos */}
        <div className="space-y-4">
          {waActive > 0 && (
            <Card
              className="cursor-pointer hover:border-green-500/30 transition-colors"
              onClick={() => navigate('/whatsapp')}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <MessageCircle size={16} className="text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium">{waActive} chats WhatsApp activos</p>
                  <p className="text-[10px] text-text-muted">
                    {extra?.waStats?.messages_today || 0} mensajes hoy
                  </p>
                </div>
              </div>
            </Card>
          )}

          {ghlActive > 0 && (
            <Card
              className="cursor-pointer hover:border-purple-500/30 transition-colors"
              onClick={() => navigate('/ghl')}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <Users size={16} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-medium">{ghlActive} conversaciones GHL activas</p>
                  <p className="text-[10px] text-text-muted">
                    {extra?.ghlStats?.messages_today || 0} mensajes hoy
                  </p>
                </div>
              </div>
            </Card>
          )}

          <Card
            className="cursor-pointer hover:border-accent/30 transition-colors"
            onClick={() => navigate('/analytics')}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <TrendingUp size={16} className="text-accent" />
              </div>
              <div>
                <p className="text-sm font-medium">Analytics detallado</p>
                <p className="text-[10px] text-text-muted">
                  Sentimiento, intents, calidad, distribuciones
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
