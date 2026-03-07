import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Save, Trash2, MessageCircle, Check, Copy, Wifi, WifiOff, QrCode,
  RefreshCw, Loader2, Smartphone, Settings, Pause, Play, Clock,
  Calendar, Zap, ChevronDown, ChevronRight,
} from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input, Textarea } from './ui/Input'

const STEPS = {
  NOT_CONFIGURED: 'not_configured',
  CONNECTING: 'connecting',
  QR_READY: 'qr_ready',
  CONNECTED: 'connected',
  ERROR: 'error',
}

const DAYS = [
  { key: 'mon', label: 'Lunes' },
  { key: 'tue', label: 'Martes' },
  { key: 'wed', label: 'Miercoles' },
  { key: 'thu', label: 'Jueves' },
  { key: 'fri', label: 'Viernes' },
  { key: 'sat', label: 'Sabado' },
  { key: 'sun', label: 'Domingo' },
]

const DEFAULT_SCHEDULE = {
  timezone: 'America/Mexico_City',
  mon: { active: true, start: '09:00', end: '18:00' },
  tue: { active: true, start: '09:00', end: '18:00' },
  wed: { active: true, start: '09:00', end: '18:00' },
  thu: { active: true, start: '09:00', end: '18:00' },
  fri: { active: true, start: '09:00', end: '17:00' },
  sat: { active: false, start: '09:00', end: '14:00' },
  sun: { active: false, start: '09:00', end: '14:00' },
}

const GHL_CHANNELS = [
  'WhatsApp', 'SMS', 'Web Chat', 'Facebook', 'Instagram', 'Email', 'Google Business',
]

export function WhatsAppConfig({ clientId, agentId }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState(STEPS.NOT_CONFIGURED)

  // Evolution connection
  const [qrCode, setQrCode] = useState(null)
  const [connectionInfo, setConnectionInfo] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const pollRef = useRef(null)

  // Control panel
  const [isPaused, setIsPaused] = useState(false)
  const [togglingPause, setTogglingPause] = useState(false)

  // Schedule
  const [scheduleEnabled, setScheduleEnabled] = useState(false)
  const [schedule, setSchedule] = useState(DEFAULT_SCHEDULE)

  // Behavior settings
  const [form, setForm] = useState({
    phone_number: '',
    auto_reply: true,
    greeting: '',
    session_timeout_minutes: 30,
    media_response: 'Solo puedo procesar mensajes de texto por ahora.',
    away_message: 'En este momento no estamos disponibles. Te responderemos en horario de atencion.',
    paused_message: 'En este momento un agente humano esta atendiendo. Te responderemos pronto.',
  })

  // GHL fields
  const [ghlForm, setGhlForm] = useState({ ghl_location_id: '', ghl_api_key: '' })
  const [ghlExpanded, setGhlExpanded] = useState(false)
  const [ghlHasConfig, setGhlHasConfig] = useState(false)

  const [activeTab, setActiveTab] = useState('control') // control | schedule | settings
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadConfig()
    return () => stopPolling()
  }, [clientId, agentId])

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function loadConfig() {
    setLoading(true)
    try {
      const data = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp`)
      if (data) {
        setConfig(data)
        setIsPaused(data.is_paused || false)
        setScheduleEnabled(!!data.schedule)
        setSchedule(data.schedule || DEFAULT_SCHEDULE)
        setForm({
          phone_number: data.phone_number || '',
          auto_reply: data.auto_reply !== false,
          greeting: data.greeting || '',
          session_timeout_minutes: data.session_timeout_minutes || 30,
          media_response: data.media_response || 'Solo puedo procesar mensajes de texto por ahora.',
          away_message: data.away_message || 'En este momento no estamos disponibles. Te responderemos en horario de atencion.',
          paused_message: data.paused_message || 'En este momento un agente humano esta atendiendo. Te responderemos pronto.',
        })
        setGhlForm({
          ghl_location_id: data.ghl_location_id || '',
          ghl_api_key: '',
        })

        if (data.provider === 'gohighlevel') {
          setGhlHasConfig(true)
          setGhlExpanded(true)
          setStep(STEPS.CONNECTED)
        } else if (data.provider === 'evolution') {
          setGhlHasConfig(!!data.ghl_location_id)
          if (data.ghl_location_id) setGhlExpanded(true)
          await checkStatus()
        }
      } else {
        await checkStatus()
      }
    } catch (err) {
      console.warn('WhatsApp config load failed:', err.message)
      await checkStatus()
    } finally {
      setLoading(false)
    }
  }

  const checkStatus = useCallback(async () => {
    try {
      const status = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp/evolution/status`)
      if (status.connected) {
        setStep(STEPS.CONNECTED)
        setConnectionInfo(status)
        setForm(f => ({
          ...f,
          phone_number: status.phone_number ? `+${status.phone_number}` : f.phone_number,
        }))
        stopPolling()
        if (!config) {
          try {
            const data = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp`)
            if (data) {
              setConfig(data)
              setIsPaused(data.is_paused || false)
              setScheduleEnabled(!!data.schedule)
              setSchedule(data.schedule || DEFAULT_SCHEDULE)
            }
          } catch { /* ignore */ }
        }
      } else if (status.status === 'not_configured') {
        setStep(STEPS.NOT_CONFIGURED)
      } else {
        if (step !== STEPS.QR_READY && step !== STEPS.CONNECTING) {
          setStep(STEPS.QR_READY)
          await refreshQR()
        }
      }
      return status
    } catch {
      return null
    }
  }, [clientId, agentId, step])

  function startPolling() {
    stopPolling()
    pollRef.current = setInterval(async () => {
      const status = await checkStatus()
      if (status?.connected) stopPolling()
    }, 3000)
  }

  async function handleConnect() {
    setConnecting(true)
    setStep(STEPS.CONNECTING)
    try {
      const data = await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp/evolution/connect`, {})
      if (data.qr_code) {
        setQrCode(data.qr_code)
        setStep(STEPS.QR_READY)
        startPolling()
      } else {
        const status = await checkStatus()
        if (!status?.connected) {
          setStep(STEPS.QR_READY)
          await refreshQR()
          startPolling()
        }
      }
    } catch (err) {
      toast.error(err.message || 'Error conectando WhatsApp')
      setStep(STEPS.ERROR)
    } finally {
      setConnecting(false)
    }
  }

  async function refreshQR() {
    try {
      const data = await api.get(`/clients/${clientId}/agents/${agentId}/whatsapp/evolution/qr`)
      if (data.qr_code) {
        setQrCode(data.qr_code)
        setStep(STEPS.QR_READY)
      } else if (data.status === 'already_connected') {
        await checkStatus()
      }
    } catch (err) {
      toast.error('Error obteniendo QR: ' + (err.message || ''))
    }
  }

  async function handleDisconnect() {
    const ok = await confirm({
      title: 'Desconectar WhatsApp',
      message: 'Se eliminara la conexion de WhatsApp. Los mensajes anteriores se mantienen.',
      confirmText: 'Desconectar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp/evolution/disconnect`)
      setConfig(null)
      setStep(STEPS.NOT_CONFIGURED)
      setConnectionInfo(null)
      setQrCode(null)
      stopPolling()
      toast.success('WhatsApp desconectado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function togglePause() {
    setTogglingPause(true)
    try {
      const newPaused = !isPaused
      await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, { is_paused: newPaused })
      setIsPaused(newPaused)
      toast.success(newPaused ? 'Agente pausado — tu controlas' : 'Agente activo — responde automaticamente')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setTogglingPause(false)
    }
  }

  async function handleSaveSettings() {
    setSaving(true)
    try {
      const provider = ghlHasConfig && !isEvoConnected ? 'gohighlevel' : 'evolution'
      const payload = {
        provider,
        ...form,
        phone_number: form.phone_number || null,
        greeting: form.greeting || null,
        schedule: scheduleEnabled ? schedule : null,
      }

      if (ghlForm.ghl_location_id) {
        payload.ghl_location_id = ghlForm.ghl_location_id
        if (ghlForm.ghl_api_key) payload.ghl_api_key = ghlForm.ghl_api_key
      }

      if (config) {
        await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      } else {
        await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      }
      toast.success('Configuracion guardada')
      await loadConfig()
    } catch (err) {
      toast.error(err.message || 'Error guardando')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveGHL() {
    if (!ghlForm.ghl_location_id) {
      toast.error('Ingresa el Location ID')
      return
    }
    setSaving(true)
    try {
      const payload = {
        provider: 'gohighlevel',
        ghl_location_id: ghlForm.ghl_location_id,
        ...form,
        phone_number: form.phone_number || null,
        greeting: form.greeting || null,
        schedule: scheduleEnabled ? schedule : null,
      }
      if (ghlForm.ghl_api_key?.trim()) payload.ghl_api_key = ghlForm.ghl_api_key.trim()

      if (config) {
        await api.patch(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      } else {
        await api.post(`/clients/${clientId}/agents/${agentId}/whatsapp`, payload)
      }
      toast.success('GoHighLevel configurado')
      setGhlHasConfig(true)
      await loadConfig()
    } catch (err) {
      toast.error(err.message || 'Error guardando GHL')
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteGHL() {
    const ok = await confirm({
      title: 'Desconectar GoHighLevel',
      message: 'Se eliminara la conexion con GoHighLevel para este agente.',
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
      setGhlHasConfig(false)
      setGhlForm({ ghl_location_id: '', ghl_api_key: '' })
      toast.success('GoHighLevel desconectado')
      await loadConfig()
    } catch (err) {
      toast.error(err.message)
    }
  }

  function updateDay(dayKey, field, value) {
    setSchedule(s => ({
      ...s,
      [dayKey]: { ...s[dayKey], [field]: value },
    }))
  }

  const webhookBase = import.meta.env.VITE_API_URL || window.location.origin + '/api'
  const webhookUrl = `${webhookBase}/webhooks/whatsapp/gohighlevel`

  function copyWebhook() {
    navigator.clipboard.writeText(webhookUrl)
    toast.success('URL copiada')
  }

  if (loading) return <p className="text-sm text-text-muted py-4">Cargando...</p>

  const isEvoConnected = step === STEPS.CONNECTED && config?.provider !== 'gohighlevel'
  const isConnected = step === STEPS.CONNECTED || ghlHasConfig

  return (
    <div className="space-y-4">
      {/* ══════════════════════════════════════════════════════
          SECCION 1: WhatsApp (Evolution API)
          ══════════════════════════════════════════════════════ */}
      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <MessageCircle size={18} className="text-green-400" />
          <h2 className="text-sm font-semibold text-text-secondary">WhatsApp</h2>
          {isEvoConnected && !isPaused && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 font-medium ml-auto flex items-center gap-1">
              <Wifi size={10} /> Activo
            </span>
          )}
          {isEvoConnected && isPaused && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 font-medium ml-auto flex items-center gap-1">
              <Pause size={10} /> Pausado
            </span>
          )}
        </div>

        {/* Connected — Profile card */}
        {isEvoConnected && (
          <div className="p-4 rounded-lg border border-green-500/30 bg-green-500/5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center shrink-0">
                {connectionInfo?.profile_pic_url ? (
                  <img src={connectionInfo.profile_pic_url} alt="" className="w-10 h-10 rounded-full" />
                ) : (
                  <Smartphone size={20} className="text-green-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-green-400 truncate">
                  {connectionInfo?.profile_name || connectionInfo?.instance_name || 'WhatsApp'}
                </p>
                <p className="text-xs text-text-muted">
                  {connectionInfo?.phone_number ? `+${connectionInfo.phone_number}` : 'Conectado via Evolution API'}
                </p>
              </div>
              <button
                type="button"
                onClick={handleDisconnect}
                className="p-2 text-red-400/60 hover:text-red-400 transition-colors"
                title="Desconectar"
              >
                <WifiOff size={16} />
              </button>
            </div>
          </div>
        )}

        {/* QR Code */}
        {step === STEPS.QR_READY && (
          <div className="p-4 rounded-lg border border-border bg-bg-primary/50 space-y-4">
            <div className="text-center space-y-2">
              <QrCode size={24} className="text-accent mx-auto" />
              <p className="text-sm text-text-secondary font-medium">Escanea el QR con WhatsApp</p>
              <p className="text-xs text-text-muted">
                WhatsApp {'>'} Menu {'>'} Dispositivos vinculados {'>'} Vincular dispositivo
              </p>
            </div>
            {qrCode && (
              <div className="flex justify-center">
                <div className="bg-white p-3 rounded-xl">
                  <img
                    src={qrCode.startsWith('data:') ? qrCode : `data:image/png;base64,${qrCode}`}
                    alt="QR WhatsApp"
                    className="w-56 h-56"
                  />
                </div>
              </div>
            )}
            <div className="flex justify-center gap-2">
              <Button variant="secondary" onClick={refreshQR} className="text-xs">
                <RefreshCw size={12} className="mr-1 inline" /> Nuevo QR
              </Button>
              <Button variant="danger" onClick={handleDisconnect} className="text-xs">
                Cancelar
              </Button>
            </div>
            <div className="flex items-center justify-center gap-2 text-xs text-text-muted">
              <Loader2 size={12} className="animate-spin" />
              Esperando conexion...
            </div>
          </div>
        )}

        {/* Connecting */}
        {step === STEPS.CONNECTING && (
          <div className="p-6 rounded-lg border border-border bg-bg-primary/50 flex flex-col items-center gap-3">
            <Loader2 size={28} className="animate-spin text-accent" />
            <p className="text-sm text-text-muted">Creando instancia...</p>
          </div>
        )}

        {/* Not configured */}
        {(step === STEPS.NOT_CONFIGURED || step === STEPS.ERROR) && !ghlHasConfig && (
          <div className="p-4 rounded-lg border border-border bg-bg-primary/50 space-y-3">
            <p className="text-xs text-text-muted">
              Conecta un numero de WhatsApp a este agente. Solo necesitas escanear un QR.
            </p>
            {step === STEPS.ERROR && (
              <p className="text-xs text-red-400">
                Error al conectar. Verifica que el servidor Evolution este activo e intenta de nuevo.
              </p>
            )}
            <Button onClick={handleConnect} disabled={connecting} className="w-full">
              {connecting ? (
                <><Loader2 size={14} className="mr-1 inline animate-spin" /> Conectando...</>
              ) : (
                <><QrCode size={14} className="mr-1 inline" /> Conectar WhatsApp</>
              )}
            </Button>
          </div>
        )}

        {/* ── Control Center — cuando hay conexion activa (Evo o GHL) ── */}
        {isConnected && (
          <>
            {/* Pause/Resume */}
            {isEvoConnected && (
              <button
                type="button"
                onClick={togglePause}
                disabled={togglingPause}
                className={`w-full p-3 rounded-lg border text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                  isPaused
                    ? 'border-green-500/30 bg-green-500/5 text-green-400 hover:bg-green-500/10'
                    : 'border-yellow-500/30 bg-yellow-500/5 text-yellow-400 hover:bg-yellow-500/10'
                }`}
              >
                {togglingPause ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : isPaused ? (
                  <><Play size={16} /> Activar agente — responder automaticamente</>
                ) : (
                  <><Pause size={16} /> Pausar agente — yo respondo</>
                )}
              </button>
            )}

            {/* Tabs */}
            <div className="flex gap-1 border-b border-border">
              {['control', 'schedule', 'settings'].map(tab => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                    activeTab === tab
                      ? 'border-accent text-accent'
                      : 'border-transparent text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {tab === 'control' && 'Mensajes'}
                  {tab === 'schedule' && 'Horario'}
                  {tab === 'settings' && 'Ajustes'}
                </button>
              ))}
            </div>

            {/* Tab: Mensajes */}
            {activeTab === 'control' && (
              <div className="space-y-3">
                <Textarea
                  label="Saludo inicial (primera vez que escribe)"
                  value={form.greeting}
                  onChange={e => setForm(f => ({ ...f, greeting: e.target.value }))}
                  rows={2}
                  placeholder="Hola! Soy el asistente de [negocio]. En que puedo ayudarte?"
                />
                <Textarea
                  label="Mensaje cuando esta pausado"
                  value={form.paused_message}
                  onChange={e => setForm(f => ({ ...f, paused_message: e.target.value }))}
                  rows={2}
                />
                <Textarea
                  label="Mensaje fuera de horario"
                  value={form.away_message}
                  onChange={e => setForm(f => ({ ...f, away_message: e.target.value }))}
                  rows={2}
                />
                <Input
                  label="Respuesta a media (audios, imagenes, etc)"
                  value={form.media_response}
                  onChange={e => setForm(f => ({ ...f, media_response: e.target.value }))}
                />
              </div>
            )}

            {/* Tab: Horario */}
            {activeTab === 'schedule' && (
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
                  <input
                    type="checkbox"
                    checked={scheduleEnabled}
                    onChange={e => setScheduleEnabled(e.target.checked)}
                    className="accent-accent"
                  />
                  <Calendar size={14} />
                  Activar horario de atencion
                </label>

                {scheduleEnabled && (
                  <div className="space-y-2 p-3 rounded-lg border border-border bg-bg-primary/50">
                    {DAYS.map(({ key, label }) => {
                      const day = schedule[key] || { active: false, start: '09:00', end: '18:00' }
                      return (
                        <div key={key} className="flex items-center gap-2">
                          <label className="flex items-center gap-2 w-28 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={day.active}
                              onChange={e => updateDay(key, 'active', e.target.checked)}
                              className="accent-green-400"
                            />
                            <span className={`text-xs ${day.active ? 'text-text-secondary' : 'text-text-muted'}`}>
                              {label}
                            </span>
                          </label>
                          {day.active ? (
                            <div className="flex items-center gap-1 flex-1">
                              <input
                                type="time"
                                value={day.start}
                                onChange={e => updateDay(key, 'start', e.target.value)}
                                className="bg-bg-secondary border border-border rounded px-2 py-1 text-xs text-text-secondary"
                              />
                              <span className="text-xs text-text-muted">a</span>
                              <input
                                type="time"
                                value={day.end}
                                onChange={e => updateDay(key, 'end', e.target.value)}
                                className="bg-bg-secondary border border-border rounded px-2 py-1 text-xs text-text-secondary"
                              />
                            </div>
                          ) : (
                            <span className="text-xs text-text-muted italic">No disponible</span>
                          )}
                        </div>
                      )
                    })}
                    <div className="pt-2 border-t border-border">
                      <label className="block text-xs text-text-muted mb-1">Zona horaria</label>
                      <select
                        value={schedule.timezone || 'America/Mexico_City'}
                        onChange={e => setSchedule(s => ({ ...s, timezone: e.target.value }))}
                        className="bg-bg-secondary border border-border rounded px-2 py-1.5 text-xs text-text-secondary w-full"
                      >
                        <option value="America/Mexico_City">Ciudad de Mexico (CST)</option>
                        <option value="America/Monterrey">Monterrey (CST)</option>
                        <option value="America/Cancun">Cancun (EST)</option>
                        <option value="America/Tijuana">Tijuana (PST)</option>
                        <option value="America/Bogota">Bogota (COT)</option>
                        <option value="America/Lima">Lima (PET)</option>
                        <option value="America/Santiago">Santiago (CLT)</option>
                        <option value="America/Argentina/Buenos_Aires">Buenos Aires (ART)</option>
                      </select>
                    </div>
                  </div>
                )}

                {!scheduleEnabled && (
                  <p className="text-xs text-text-muted">
                    Sin horario configurado — el agente responde 24/7.
                  </p>
                )}
              </div>
            )}

            {/* Tab: Ajustes */}
            {activeTab === 'settings' && (
              <div className="space-y-3">
                <Input
                  label="Numero de WhatsApp"
                  value={form.phone_number}
                  onChange={e => setForm(f => ({ ...f, phone_number: e.target.value }))}
                  placeholder="+5215551234567"
                />
                <Input
                  label="Timeout de sesion (minutos)"
                  type="number"
                  value={form.session_timeout_minutes}
                  onChange={e => setForm(f => ({ ...f, session_timeout_minutes: parseInt(e.target.value) || 30 }))}
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
            )}

            {/* Save button */}
            <div className="pt-2">
              <Button onClick={handleSaveSettings} disabled={saving} className="w-full">
                <Save size={14} className="mr-1 inline" />
                {saving ? 'Guardando...' : 'Guardar configuracion'}
              </Button>
            </div>
          </>
        )}
      </Card>

      {/* ══════════════════════════════════════════════════════
          SECCION 2: GoHighLevel (Multi-canal)
          ══════════════════════════════════════════════════════ */}
      <Card className="space-y-3">
        <button
          type="button"
          onClick={() => setGhlExpanded(!ghlExpanded)}
          className="flex items-center gap-2 w-full text-left"
        >
          {ghlExpanded ? <ChevronDown size={16} className="text-text-muted" /> : <ChevronRight size={16} className="text-text-muted" />}
          <Zap size={18} className="text-orange-400" />
          <h2 className="text-sm font-semibold text-text-secondary">GoHighLevel</h2>
          <span className="text-[10px] text-text-muted ml-1">Multi-canal</span>
          {ghlHasConfig && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-medium ml-auto flex items-center gap-1">
              <Check size={10} /> Conectado
            </span>
          )}
        </button>

        {ghlExpanded && (
          <div className="space-y-3">
            <p className="text-xs text-text-muted">
              Conecta GoHighLevel para responder automaticamente en todos los canales: WhatsApp, SMS, Web Chat, Facebook, Instagram y mas.
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
                value={ghlForm.ghl_location_id}
                onChange={e => setGhlForm(f => ({ ...f, ghl_location_id: e.target.value }))}
                placeholder="ve9EPM428h8vShlRW1KT"
              />
              <div>
                <label className="block text-xs text-text-muted mb-1">API Key / Private Integration Token</label>
                {config?.has_ghl_api_key && !ghlForm.ghl_api_key ? (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-sm flex-1">
                      <Check size={14} className="text-success" />
                      <span className="text-success">Configurada</span>
                    </div>
                    <Button variant="secondary" onClick={() => setGhlForm(f => ({ ...f, ghl_api_key: ' ' }))} className="text-xs px-3">
                      Cambiar
                    </Button>
                  </div>
                ) : (
                  <Input
                    type="password"
                    value={ghlForm.ghl_api_key}
                    onChange={e => setGhlForm(f => ({ ...f, ghl_api_key: e.target.value }))}
                    placeholder="pit-xxxxxxxx..."
                  />
                )}
              </div>

              {/* Webhook URL */}
              <div className="p-3 rounded-lg border border-border bg-bg-secondary/50">
                <label className="block text-xs text-text-muted mb-1">Webhook URL (pegar en GHL {'>'} Settings {'>'} Webhooks)</label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs font-mono text-accent bg-bg-secondary px-3 py-2 rounded overflow-x-auto">
                    {webhookUrl}
                  </code>
                  <button type="button" onClick={copyWebhook} className="p-2 text-text-muted hover:text-accent transition-colors" title="Copiar">
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
              <Button onClick={handleSaveGHL} disabled={saving} className="flex-1">
                <Save size={14} className="mr-1 inline" />
                {saving ? 'Guardando...' : ghlHasConfig ? 'Actualizar GHL' : 'Conectar GHL'}
              </Button>
              {ghlHasConfig && (
                <Button variant="danger" onClick={handleDeleteGHL} className="text-xs px-3">
                  <Trash2 size={14} />
                </Button>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
