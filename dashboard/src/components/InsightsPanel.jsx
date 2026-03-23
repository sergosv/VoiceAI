/**
 * Panel de Insights + Prompt Tuner para agentes.
 * Muestra insights cross-call y sugerencias de mejora al prompt.
 */
import { useState, useEffect, useCallback } from 'react'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import {
  Lightbulb, TrendingUp, AlertTriangle, MessageSquare, Zap,
  RefreshCw, Check, X, Copy, ChevronDown, ChevronRight,
  Brain, BarChart3, HelpCircle,
} from 'lucide-react'
import { api } from '../lib/api'

// Iconos y colores por tipo de insight
const INSIGHT_TYPES = {
  faq: { icon: HelpCircle, color: 'text-blue-400', bg: 'bg-blue-500/10', label: 'Pregunta frecuente' },
  topic_trend: { icon: TrendingUp, color: 'text-green-400', bg: 'bg-green-500/10', label: 'Tema recurrente' },
  drop_point: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Punto de abandono' },
  prompt_suggestion: { icon: Lightbulb, color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Sugerencia de prompt' },
  tool_usage: { icon: Zap, color: 'text-purple-400', bg: 'bg-purple-500/10', label: 'Uso de herramientas' },
  sentiment_pattern: { icon: BarChart3, color: 'text-cyan-400', bg: 'bg-cyan-500/10', label: 'Patrón de sentimiento' },
}

export default function InsightsPanel({ clientId, agentId }) {
  const [insights, setInsights] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [expandedInsight, setExpandedInsight] = useState(null)
  const [copiedId, setCopiedId] = useState(null)

  const loadInsights = useCallback(async () => {
    if (!clientId || !agentId) return
    try {
      setLoading(true)
      const res = await api.get(`/clients/${clientId}/agents/${agentId}/insights`)
      setInsights(res.data)
    } catch (err) {
      console.error('Error loading insights:', err)
    } finally {
      setLoading(false)
    }
  }, [clientId, agentId])

  useEffect(() => { loadInsights() }, [loadInsights])

  const generateInsights = async () => {
    try {
      setGenerating(true)
      const res = await api.post(`/clients/${clientId}/agents/${agentId}/insights/generate`)
      if (res.data.generated > 0) {
        await loadInsights()
      }
    } catch (err) {
      console.error('Error generating insights:', err)
    } finally {
      setGenerating(false)
    }
  }

  const loadSuggestions = async () => {
    try {
      setLoadingSuggestions(true)
      const res = await api.get(`/clients/${clientId}/agents/${agentId}/prompt-suggestions`)
      setSuggestions(res.data)
    } catch (err) {
      console.error('Error loading suggestions:', err)
    } finally {
      setLoadingSuggestions(false)
    }
  }

  const dismissInsight = async (id) => {
    try {
      await api.put(`/clients/${clientId}/agents/${agentId}/insights/${id}/dismiss`)
      setInsights(prev => prev.filter(i => i.id !== id))
    } catch (err) {
      console.error('Error dismissing insight:', err)
    }
  }

  const applyInsight = async (id) => {
    try {
      await api.put(`/clients/${clientId}/agents/${agentId}/insights/${id}/apply`)
      setInsights(prev => prev.map(i => i.id === id ? { ...i, status: 'applied' } : i))
    } catch (err) {
      console.error('Error applying insight:', err)
    }
  }

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Agrupar insights por tipo
  const grouped = {}
  for (const ins of insights) {
    const type = ins.insight_type || 'other'
    if (!grouped[type]) grouped[type] = []
    grouped[type].push(ins)
  }

  if (loading) {
    return <div className="flex items-center justify-center py-12 text-gray-400">Cargando insights...</div>
  }

  return (
    <div className="space-y-6">
      {/* ── Prompt Suggestions ── */}
      <Card className="bg-[#12121a] border border-gray-700/50">
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-yellow-400" />
              <h3 className="text-white font-semibold">Sugerencias de mejora al prompt</h3>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={loadSuggestions}
              disabled={loadingSuggestions}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loadingSuggestions ? 'animate-spin' : ''}`} />
              {loadingSuggestions ? 'Analizando...' : 'Analizar'}
            </Button>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Analiza las métricas de calidad y sentimiento para generar sugerencias específicas de mejora.
          </p>

          {suggestions.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">
              Presiona "Analizar" para generar sugerencias basadas en las llamadas recientes.
            </p>
          ) : (
            <div className="space-y-3">
              {suggestions.map((s, idx) => (
                <div key={idx} className="border border-gray-700/50 rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          s.impact === 'high' ? 'bg-red-500/20 text-red-400' :
                          s.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-gray-500/20 text-gray-400'
                        }`}>
                          {s.impact === 'high' ? 'Alto impacto' : s.impact === 'medium' ? 'Medio' : 'Bajo'}
                        </span>
                        <span className="text-xs text-gray-500">{s.category}</span>
                      </div>
                      <p className="text-sm text-white font-medium">{s.title}</p>
                      <p className="text-xs text-gray-400 mt-1">{s.current_issue}</p>
                    </div>
                  </div>
                  {s.suggestion && (
                    <div className="mt-2 bg-[#0a0a0f] rounded p-2 border border-gray-800">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500">Agregar al prompt:</span>
                        <button
                          onClick={() => copyToClipboard(s.suggestion, `sug-${idx}`)}
                          className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                        >
                          {copiedId === `sug-${idx}` ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                          {copiedId === `sug-${idx}` ? 'Copiado' : 'Copiar'}
                        </button>
                      </div>
                      <p className="text-sm text-gray-300 font-mono">{s.suggestion}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* ── Insights Cross-Call ── */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Insights de Conversaciones</h3>
          <p className="text-sm text-gray-400 mt-1">
            Patrones detectados automáticamente del análisis de llamadas recientes.
          </p>
        </div>
        <Button
          onClick={generateInsights}
          disabled={generating}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
          {generating ? 'Analizando...' : 'Generar Insights'}
        </Button>
      </div>

      {insights.length === 0 ? (
        <Card className="bg-[#12121a] border border-gray-700/50 p-8 text-center">
          <Lightbulb className="w-12 h-12 mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 mb-2">No hay insights todavía</p>
          <p className="text-sm text-gray-500">
            Necesitas al menos 5 llamadas completadas para que el sistema detecte patrones.
            Presiona "Generar Insights" para analizar las llamadas existentes.
          </p>
        </Card>
      ) : (
        Object.entries(grouped).map(([type, typeInsights]) => {
          const typeInfo = INSIGHT_TYPES[type] || INSIGHT_TYPES.topic_trend
          const TypeIcon = typeInfo.icon
          return (
            <div key={type} className="space-y-2">
              <h4 className="text-sm font-medium text-gray-400 uppercase tracking-wider px-1 flex items-center gap-2">
                <TypeIcon className={`w-4 h-4 ${typeInfo.color}`} />
                {typeInfo.label} ({typeInsights.length})
              </h4>
              {typeInsights.map(ins => (
                <Card
                  key={ins.id}
                  className={`bg-[#12121a] border ${ins.status === 'applied' ? 'border-green-500/30 opacity-60' : 'border-gray-700/50'}`}
                >
                  <div
                    className="flex items-start gap-3 p-3 cursor-pointer hover:bg-white/[0.02]"
                    onClick={() => setExpandedInsight(expandedInsight === ins.id ? null : ins.id)}
                  >
                    <div className={`p-1.5 rounded ${typeInfo.bg} flex-shrink-0 mt-0.5`}>
                      <TypeIcon className={`w-4 h-4 ${typeInfo.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm text-white font-medium">{ins.title}</p>
                        {ins.status === 'applied' && (
                          <span className="text-xs text-green-400 flex items-center gap-1">
                            <Check className="w-3 h-3" /> Aplicado
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5 truncate">{ins.description}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-gray-500">
                          {ins.frequency}x detectado
                        </span>
                        <span className="text-xs text-gray-500">
                          Confianza: {Math.round((ins.confidence || 0) * 100)}%
                        </span>
                        <span className="text-xs text-gray-500">
                          {ins.calls_analyzed} llamadas analizadas
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                      {ins.status !== 'applied' && (
                        <>
                          <button
                            onClick={() => applyInsight(ins.id)}
                            className="p-1 text-gray-500 hover:text-green-400"
                            title="Marcar como aplicado"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => dismissInsight(ins.id)}
                            className="p-1 text-gray-500 hover:text-red-400"
                            title="Descartar"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      {expandedInsight === ins.id ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
                    </div>
                  </div>

                  {expandedInsight === ins.id && (
                    <div className="border-t border-gray-800 p-3 space-y-3">
                      <p className="text-sm text-gray-300">{ins.description}</p>

                      {ins.suggested_response && (
                        <div className="bg-[#0a0a0f] rounded p-2 border border-gray-800">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-gray-500">Respuesta sugerida:</span>
                            <button
                              onClick={() => copyToClipboard(ins.suggested_response, ins.id)}
                              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                            >
                              {copiedId === ins.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                              {copiedId === ins.id ? 'Copiado' : 'Copiar'}
                            </button>
                          </div>
                          <p className="text-sm text-gray-300">{ins.suggested_response}</p>
                        </div>
                      )}

                      {ins.suggested_prompt_addition && (
                        <div className="bg-[#0a0a0f] rounded p-2 border border-yellow-500/20">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-yellow-400">Agregar al prompt:</span>
                            <button
                              onClick={() => copyToClipboard(ins.suggested_prompt_addition, `prompt-${ins.id}`)}
                              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                            >
                              {copiedId === `prompt-${ins.id}` ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                              {copiedId === `prompt-${ins.id}` ? 'Copiado' : 'Copiar'}
                            </button>
                          </div>
                          <p className="text-sm text-yellow-200 font-mono">{ins.suggested_prompt_addition}</p>
                        </div>
                      )}

                      {ins.evidence && ins.evidence.example_queries && (
                        <div>
                          <span className="text-xs text-gray-500">Ejemplos detectados:</span>
                          <ul className="mt-1 space-y-1">
                            {ins.evidence.example_queries.map((q, i) => (
                              <li key={i} className="text-xs text-gray-400 pl-2 border-l border-gray-700">"{q}"</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )
        })
      )}
    </div>
  )
}
