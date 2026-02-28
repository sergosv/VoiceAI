import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import {
  ArrowLeft, Play, Pause, Save, Plus, Trash2, Phone,
  CheckCircle, XCircle, Clock, AlertTriangle, ChevronDown, ChevronUp,
  User, Mail, MessageSquare, TrendingUp,
} from 'lucide-react'

const statusLabels = {
  draft: 'Borrador',
  scheduled: 'Programada',
  running: 'En ejecucion',
  paused: 'Pausada',
  completed: 'Completada',
}

const callStatusIcons = {
  pending: <Clock size={14} className="text-text-muted" />,
  calling: <Phone size={14} className="text-accent animate-pulse" />,
  completed: <CheckCircle size={14} className="text-success" />,
  failed: <XCircle size={14} className="text-danger" />,
  no_answer: <AlertTriangle size={14} className="text-warning" />,
  busy: <AlertTriangle size={14} className="text-warning" />,
  retry: <Clock size={14} className="text-warning" />,
}

const callStatusLabels = {
  pending: 'Pendiente',
  calling: 'Llamando',
  completed: 'Completada',
  failed: 'Fallida',
  no_answer: 'Sin respuesta',
  busy: 'Ocupado',
  retry: 'Reintento',
}

// Badges de resultado del análisis IA
const analysisResultConfig = {
  demo_agendada: { label: 'Demo agendada', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
  interesado: { label: 'Interesado', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  no_interesado: { label: 'No interesado', color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' },
  no_contactar: { label: 'No contactar', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
  voicemail: { label: 'Voicemail', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  no_answer: { label: 'Sin respuesta', color: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
}

const sentimentConfig = {
  positive: { label: 'Positivo', color: 'text-green-400' },
  neutral: { label: 'Neutral', color: 'text-zinc-400' },
  negative: { label: 'Negativo', color: 'text-red-400' },
}

function AnalysisResultBadge({ result }) {
  const config = analysisResultConfig[result]
  if (!config) return <span className="text-xs text-text-muted">{result}</span>
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${config.color}`}>
      {config.label}
    </span>
  )
}

function AnalysisSummaryCards({ calls }) {
  const analyzed = calls.filter(c => c.analysis_data?.result)
  if (analyzed.length === 0) return null

  const counts = {}
  for (const c of analyzed) {
    const r = c.analysis_data.result
    counts[r] = (counts[r] || 0) + 1
  }

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .map(([result, count]) => {
          const config = analysisResultConfig[result]
          if (!config) return null
          return (
            <div key={result} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${config.color}`}>
              <span className="text-sm font-semibold">{count}</span>
              <span className="text-xs">{config.label}</span>
            </div>
          )
        })}
    </div>
  )
}

function ExpandedAnalysis({ analysis }) {
  if (!analysis) return null
  return (
    <div className="px-4 py-3 bg-bg-primary/50 border-t border-border space-y-3">
      {/* Resumen */}
      {analysis.summary && (
        <div>
          <span className="text-xs text-text-muted font-medium">Resumen</span>
          <p className="text-sm text-text-secondary mt-0.5">{analysis.summary}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-6">
        {/* Sentimiento */}
        {analysis.sentiment && (
          <div>
            <span className="text-xs text-text-muted font-medium">Sentimiento</span>
            <p className={`text-sm mt-0.5 ${sentimentConfig[analysis.sentiment]?.color || 'text-text-secondary'}`}>
              {sentimentConfig[analysis.sentiment]?.label || analysis.sentiment}
            </p>
          </div>
        )}

        {/* Confianza */}
        {analysis.confidence != null && (
          <div>
            <span className="text-xs text-text-muted font-medium">Confianza</span>
            <p className="text-sm text-text-secondary mt-0.5">{Math.round(analysis.confidence * 100)}%</p>
          </div>
        )}

        {/* Contacto extraido */}
        {(analysis.contact_name || analysis.contact_email) && (
          <div>
            <span className="text-xs text-text-muted font-medium">Contacto</span>
            <div className="flex items-center gap-3 mt-0.5">
              {analysis.contact_name && (
                <span className="flex items-center gap-1 text-sm text-text-secondary">
                  <User size={12} /> {analysis.contact_name}
                </span>
              )}
              {analysis.contact_email && (
                <span className="flex items-center gap-1 text-sm text-text-secondary">
                  <Mail size={12} /> {analysis.contact_email}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Objeciones */}
      {analysis.objections?.length > 0 && (
        <div>
          <span className="text-xs text-text-muted font-medium">Objeciones</span>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {analysis.objections.map((obj, i) => (
              <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-red-500/10 text-red-400 border border-red-500/20">
                {obj}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Siguiente paso */}
      {analysis.next_step && (
        <div>
          <span className="text-xs text-text-muted font-medium">Siguiente paso</span>
          <p className="text-sm text-accent mt-0.5 flex items-center gap-1">
            <TrendingUp size={12} /> {analysis.next_step}
          </p>
        </div>
      )}
    </div>
  )
}

export function CampaignDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const [campaign, setCampaign] = useState(null)
  const [calls, setCalls] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showAddContacts, setShowAddContacts] = useState(false)
  const [form, setForm] = useState({})
  const [expandedRow, setExpandedRow] = useState(null)

  useEffect(() => {
    loadData()
  }, [id])

  // Auto-refresh cuando running
  useEffect(() => {
    if (campaign?.status !== 'running') return
    const interval = setInterval(loadData, 5000)
    return () => clearInterval(interval)
  }, [campaign?.status])

  async function loadData() {
    try {
      const [camp, campCalls] = await Promise.all([
        api.get(`/campaigns/${id}`),
        api.get(`/campaigns/${id}/calls`),
      ])
      setCampaign(camp)
      setCalls(campCalls)
      setForm({
        name: camp.name,
        description: camp.description || '',
        script: camp.script,
        max_concurrent: camp.max_concurrent,
        retry_attempts: camp.retry_attempts,
      })
    } catch (e) {
      toast.error(e.message)
      navigate('/campaigns')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      const updated = await api.patch(`/campaigns/${id}`, form)
      setCampaign(updated)
      toast.success('Campana actualizada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleStart() {
    try {
      const updated = await api.post(`/campaigns/${id}/start`)
      setCampaign(updated)
      toast.success('Campana iniciada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handlePause() {
    try {
      const updated = await api.post(`/campaigns/${id}/pause`)
      setCampaign(updated)
      toast.success('Campana pausada')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleRestart() {
    const ok = await confirm({
      title: 'Relanzar campana',
      message: 'Se resetearan todas las llamadas a pendiente. Continuar?',
      confirmText: 'Relanzar',
      variant: 'warning',
    })
    if (!ok) return
    try {
      const updated = await api.post(`/campaigns/${id}/restart`)
      setCampaign(updated)
      await loadData()
      toast.success('Campana reiniciada — lista para lanzar')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Eliminar campana',
      message: 'Se eliminara la campana y todas sus llamadas. Esta accion es irreversible.',
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/campaigns/${id}`)
      toast.success('Campana eliminada')
      navigate('/campaigns')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleRemoveContact(callId, phone) {
    const ok = await confirm({
      title: 'Eliminar contacto',
      message: `Eliminar ${phone} de la campana?`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/campaigns/${id}/calls/${callId}`)
      await loadData()
      toast.success('Contacto eliminado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  if (loading) return <PageLoader />
  if (!campaign) return null

  const editable = ['draft', 'paused', 'completed'].includes(campaign.status)
  const progress = campaign.total_contacts > 0
    ? Math.round((campaign.completed_contacts / campaign.total_contacts) * 100)
    : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate('/campaigns')}>
            <ArrowLeft size={16} />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{campaign.name}</h1>
            <Badge variant={campaign.status}>{statusLabels[campaign.status]}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {campaign.status === 'running' ? (
            <Button variant="secondary" onClick={handlePause}>
              <Pause size={16} className="mr-1" /> Pausar
            </Button>
          ) : (
            <>
              {['paused', 'completed'].includes(campaign.status) && (
                <Button variant="secondary" onClick={handleRestart}>
                  <Play size={16} className="mr-1" /> Relanzar
                </Button>
              )}
              {['draft', 'paused', 'scheduled'].includes(campaign.status) && campaign.total_contacts > 0 && (
                <Button onClick={handleStart}>
                  <Play size={16} className="mr-1" />
                  {campaign.status === 'paused' ? 'Reanudar' : 'Iniciar'}
                </Button>
              )}
            </>
          )}
          {campaign.status !== 'running' && (
            <Button variant="secondary" className="text-danger" onClick={handleDelete}>
              <Trash2 size={16} />
            </Button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Progreso</span>
          <span className="text-sm text-text-muted">{progress}%</span>
        </div>
        <div className="w-full bg-bg-primary rounded-full h-3">
          <div
            className="bg-accent h-3 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-text-muted">
          <span>{campaign.completed_contacts} / {campaign.total_contacts} completadas</span>
          <span>{campaign.successful_contacts} exitosas</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config */}
        <Card className="lg:col-span-1">
          <h2 className="text-lg font-semibold mb-4">Configuracion</h2>
          <div className="space-y-4">
            <Input
              label="Nombre"
              value={form.name || ''}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              disabled={!editable}
            />
            <Input
              label="Descripcion"
              value={form.description || ''}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              disabled={!editable}
            />
            <div>
              <label className="block text-xs text-text-muted mb-1">Script del agente</label>
              <textarea
                value={form.script || ''}
                onChange={e => setForm(f => ({ ...f, script: e.target.value }))}
                disabled={!editable}
                className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm resize-y min-h-[100px] focus:outline-none focus:border-accent disabled:opacity-50"
                rows={5}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Simultaneas"
                type="number"
                value={form.max_concurrent || 1}
                onChange={e => setForm(f => ({ ...f, max_concurrent: parseInt(e.target.value) || 1 }))}
                disabled={!editable}
              />
              <Input
                label="Reintentos"
                type="number"
                value={form.retry_attempts || 0}
                onChange={e => setForm(f => ({ ...f, retry_attempts: parseInt(e.target.value) || 0 }))}
                disabled={!editable}
              />
            </div>
            {editable && (
              <Button onClick={handleSave} disabled={saving} className="w-full">
                <Save size={14} className="mr-1" /> {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            )}
          </div>
        </Card>

        {/* Lista de contactos/llamadas */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Contactos ({calls.length})</h2>
            {editable && (
              <Button variant="secondary" onClick={() => setShowAddContacts(true)}>
                <Plus size={16} className="mr-1" /> Agregar
              </Button>
            )}
          </div>
          {calls.length === 0 ? (
            <p className="text-text-muted text-center py-8">
              Sin contactos. Agrega contactos para iniciar la campana.
            </p>
          ) : (
            <>
              {/* Resumen por resultado de análisis IA */}
              <AnalysisSummaryCards calls={calls} />

              {/* Resumen rápido por status */}
              <div className="flex gap-4 mb-4 text-xs">
                <span className="text-text-muted">
                  {calls.filter(c => c.status === 'calling').length} en llamada
                </span>
                <span className="text-success">
                  {calls.filter(c => c.status === 'completed').length} completadas
                </span>
                <span className="text-danger">
                  {calls.filter(c => c.status === 'failed').length} fallidas
                </span>
                <span className="text-warning">
                  {calls.filter(c => c.status === 'no_answer').length} sin respuesta
                </span>
              </div>
              <Table>
                <thead>
                  <tr>
                    <Th>Telefono</Th>
                    <Th>Estado</Th>
                    <Th>Intento</Th>
                    <Th>Resultado</Th>
                    {editable && <Th></Th>}
                  </tr>
                </thead>
                <tbody>
                  {calls.map(c => {
                    const hasAnalysis = !!c.analysis_data?.result
                    const isExpanded = expandedRow === c.id
                    return (
                      <React.Fragment key={c.id}>
                        <tr className="group">
                          <Td>
                            <span className="font-mono text-xs">{c.phone}</span>
                          </Td>
                          <Td>
                            <span className="flex items-center gap-1 text-xs">
                              {callStatusIcons[c.status]}
                              {callStatusLabels[c.status] || c.status}
                            </span>
                          </Td>
                          <Td>
                            <span className="text-xs">{c.attempt}</span>
                          </Td>
                          <Td>
                            {hasAnalysis ? (
                              <button
                                onClick={() => setExpandedRow(isExpanded ? null : c.id)}
                                className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
                              >
                                <AnalysisResultBadge result={c.analysis_data.result} />
                                {isExpanded
                                  ? <ChevronUp size={12} className="text-text-muted" />
                                  : <ChevronDown size={12} className="text-text-muted" />
                                }
                              </button>
                            ) : (
                              <span className="text-xs text-text-secondary line-clamp-2" title={c.result_summary || ''}>
                                {c.result_summary || '\u2014'}
                              </span>
                            )}
                          </Td>
                          {editable && (
                            <Td>
                              <button
                                onClick={() => handleRemoveContact(c.id, c.phone)}
                                className="text-text-muted hover:text-danger transition-colors p-1"
                                title="Eliminar contacto"
                              >
                                <Trash2 size={14} />
                              </button>
                            </Td>
                          )}
                        </tr>
                        {isExpanded && hasAnalysis && (
                          <tr>
                            <td colSpan={editable ? 5 : 4} className="p-0">
                              <ExpandedAnalysis analysis={c.analysis_data} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </Table>
            </>
          )}
        </Card>
      </div>

      {showAddContacts && (
        <AddContactsModal
          campaignId={id}
          onClose={() => setShowAddContacts(false)}
          onAdded={() => {
            setShowAddContacts(false)
            loadData()
            toast.success('Contactos agregados')
          }}
        />
      )}
    </div>
  )
}

function AddContactsModal({ campaignId, onClose, onAdded }) {
  const [phones, setPhones] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    const phoneNumbers = phones
      .split(/[\n,;]+/)
      .map(p => p.trim())
      .filter(Boolean)
    if (!phoneNumbers.length) return toast.error('Ingresa al menos un numero')
    setSaving(true)
    try {
      await api.post(`/campaigns/${campaignId}/contacts`, { phone_numbers: phoneNumbers })
      onAdded()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Agregar contactos" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-text-muted mb-1">
            Numeros de telefono (uno por linea, o separados por comas)
          </label>
          <textarea
            value={phones}
            onChange={e => setPhones(e.target.value)}
            className="w-full bg-bg-primary border border-border rounded-lg p-2 text-sm font-mono resize-y min-h-[120px] focus:outline-none focus:border-accent"
            rows={6}
            placeholder={"+5215512345678\n+5215587654321"}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Agregando...' : 'Agregar'}</Button>
        </div>
      </form>
    </Modal>
  )
}
