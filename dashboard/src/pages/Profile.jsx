import { useEffect, useState, useMemo } from 'react'
import {
  User, Mail, Lock, Globe, Clock, HelpCircle, Save, ChevronDown,
  ChevronUp, ExternalLink, Shield,
} from 'lucide-react'
import { api } from '../lib/api'
import { supabase } from '../lib/supabase'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'

/* ─────────────────────── Constants ─────────────────────── */

const TIMEZONES = [
  { value: 'America/Mexico_City', label: 'Ciudad de Mexico (UTC-6)' },
  { value: 'America/Monterrey', label: 'Monterrey (UTC-6)' },
  { value: 'America/Cancun', label: 'Cancun (UTC-5)' },
  { value: 'America/Tijuana', label: 'Tijuana (UTC-8)' },
  { value: 'America/Hermosillo', label: 'Hermosillo (UTC-7)' },
  { value: 'America/Chihuahua', label: 'Chihuahua (UTC-6)' },
  { value: 'America/Bogota', label: 'Bogota (UTC-5)' },
  { value: 'America/Lima', label: 'Lima (UTC-5)' },
  { value: 'America/Santiago', label: 'Santiago (UTC-3)' },
  { value: 'America/Buenos_Aires', label: 'Buenos Aires (UTC-3)' },
  { value: 'America/Sao_Paulo', label: 'Sao Paulo (UTC-3)' },
  { value: 'America/New_York', label: 'New York (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (UTC-8)' },
  { value: 'America/Chicago', label: 'Chicago (UTC-6)' },
  { value: 'Europe/Madrid', label: 'Madrid (UTC+1)' },
  { value: 'UTC', label: 'UTC' },
]

const LANGUAGES = [
  { value: 'es', label: 'Espanol' },
  { value: 'en', label: 'English' },
]

const FAQ_ITEMS = [
  {
    q: 'Como creo mi primer agente?',
    a: 'Ve a Configuracion > Crear Agente en el menu lateral. El asistente te guiara paso a paso para configurar nombre, voz, prompt del sistema y documentos de conocimiento.',
  },
  {
    q: 'Como conecto WhatsApp?',
    a: 'En la seccion de Configuracion > Agentes, selecciona tu agente y ve a la pestana WhatsApp. Necesitaras una instancia de Evolution API configurada con tu numero de WhatsApp Business.',
  },
  {
    q: 'Como funciona el billing?',
    a: 'Cada llamada, mensaje de WhatsApp y uso de API consume creditos. Ve a Cuenta > Creditos para ver tu saldo, comprar creditos o configurar auto-recarga.',
  },
  {
    q: 'Como uso el Flow Builder?',
    a: 'Selecciona un agente en Configuracion > Agentes y haz clic en "Flow Builder". Podras crear flujos de conversacion visuales con nodos de decision, acciones y respuestas.',
  },
  {
    q: 'Como configuro webhooks?',
    a: 'Ve a Configuracion > Integraciones > API. Ahi puedes registrar URLs de webhook para recibir notificaciones en tiempo real de llamadas, mensajes y eventos.',
  },
]

/* ─────────────────── Password Strength ──────────────────── */

function getPasswordStrength(password) {
  if (!password) return { level: 0, label: '', color: '' }
  let score = 0
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^A-Za-z0-9]/.test(password)) score++

  if (score <= 1) return { level: 1, label: 'Debil', color: 'bg-danger' }
  if (score <= 3) return { level: 2, label: 'Media', color: 'bg-warning' }
  return { level: 3, label: 'Fuerte', color: 'bg-success' }
}

function PasswordStrength({ password }) {
  const strength = getPasswordStrength(password)
  if (!password) return null

  return (
    <div className="mt-2">
      <div className="flex gap-1 mb-1">
        {[1, 2, 3].map(i => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= strength.level ? strength.color : 'bg-border'
            }`}
          />
        ))}
      </div>
      <p className="text-xs text-text-muted">{strength.label}</p>
    </div>
  )
}

/* ───────────────────── FAQ Accordion ────────────────────── */

function FaqItem({ question, answer }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-border rounded-lg">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-3 text-sm text-text-primary hover:bg-bg-hover transition-colors cursor-pointer rounded-lg"
      >
        <span className="text-left">{question}</span>
        {open ? <ChevronUp size={16} className="text-text-muted flex-shrink-0 ml-2" /> : <ChevronDown size={16} className="text-text-muted flex-shrink-0 ml-2" />}
      </button>
      {open && (
        <div className="px-4 pb-3 text-sm text-text-secondary leading-relaxed">
          {answer}
        </div>
      )}
    </div>
  )
}

/* ──────────────────── Section Header ────────────────────── */

function SectionHeader({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={18} className="text-accent" />
      <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
    </div>
  )
}

/* ═══════════════════════ Main Page ═══════════════════════ */

export function Profile() {
  const { user } = useAuth()
  const { addToast } = useToast()

  // Profile state
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Editable fields
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')

  // Password
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  // Preferences
  const [timezone, setTimezone] = useState('America/Mexico_City')
  const [language, setLanguage] = useState('es')
  const [savingPrefs, setSavingPrefs] = useState(false)

  // Initials
  const initials = useMemo(() => {
    if (displayName) {
      const parts = displayName.trim().split(/\s+/)
      return parts.length >= 2
        ? (parts[0][0] + parts[1][0]).toUpperCase()
        : parts[0].substring(0, 2).toUpperCase()
    }
    return user?.email?.[0]?.toUpperCase() || '?'
  }, [displayName, user])

  // Fetch profile
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await api.get('/auth/profile')
        if (cancelled) return
        setProfile(data)
        setDisplayName(data.display_name || '')
        setEmail(data.email || '')
        setTimezone(data.timezone || 'America/Mexico_City')
        setLanguage(data.language || 'es')
      } catch (err) {
        addToast('Error cargando perfil: ' + err.message, 'error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  // Save profile info
  async function handleSaveProfile() {
    setSaving(true)
    try {
      await api.patch('/auth/profile', { display_name: displayName })

      // Si cambio el email, actualizar en Supabase Auth
      if (email !== profile.email) {
        const { error } = await supabase.auth.updateUser({ email })
        if (error) throw new Error(error.message)
        addToast('Se envio un correo de confirmacion al nuevo email', 'info')
      }

      addToast('Perfil actualizado', 'success')
      setProfile(prev => ({ ...prev, display_name: displayName, email }))
    } catch (err) {
      addToast('Error: ' + err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  // Change password
  async function handleChangePassword() {
    if (newPassword !== confirmPassword) {
      addToast('Las contrasenas no coinciden', 'error')
      return
    }
    if (newPassword.length < 8) {
      addToast('La contrasena debe tener al menos 8 caracteres', 'error')
      return
    }

    setChangingPassword(true)
    try {
      // Re-autenticar con password actual para validar
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: profile.email,
        password: currentPassword,
      })
      if (signInError) {
        addToast('Contrasena actual incorrecta', 'error')
        return
      }

      // Actualizar password
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) throw new Error(error.message)

      addToast('Contrasena actualizada correctamente', 'success')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      addToast('Error: ' + err.message, 'error')
    } finally {
      setChangingPassword(false)
    }
  }

  // Save preferences
  async function handleSavePrefs() {
    setSavingPrefs(true)
    try {
      await api.patch('/auth/profile', { timezone, language })
      addToast('Preferencias guardadas', 'success')
      setProfile(prev => ({ ...prev, timezone, language }))
    } catch (err) {
      addToast('Error: ' + err.message, 'error')
    } finally {
      setSavingPrefs(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Mi Perfil</h1>

      {/* ───── Section 1: Profile Info ───── */}
      <Card>
        <SectionHeader icon={User} title="Informacion Personal" />

        {/* Avatar + badges */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center text-xl font-bold text-accent border-2 border-accent/30">
            {initials}
          </div>
          <div>
            <p className="text-lg font-semibold text-text-primary">
              {displayName || profile?.email}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={profile?.role || 'client'}>{profile?.role || 'client'}</Badge>
              {profile?.client_name && (
                <span className="text-xs text-text-muted">{profile.client_name}</span>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <Input
            label="Nombre"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            placeholder="Tu nombre completo"
          />

          <Input
            label="Email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="correo@ejemplo.com"
          />

          {profile?.role && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-text-secondary">Rol</label>
              <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary border border-border rounded-lg text-sm text-text-muted">
                <Shield size={14} />
                {profile.role === 'admin' ? 'Administrador' : 'Cliente'}
                <span className="text-text-muted text-xs">(solo lectura)</span>
              </div>
            </div>
          )}

          {profile?.client_name && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm text-text-secondary">Organizacion</label>
              <div className="px-3 py-2 bg-bg-secondary border border-border rounded-lg text-sm text-text-muted">
                {profile.client_name}
                <span className="text-text-muted text-xs ml-2">(solo lectura)</span>
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleSaveProfile} disabled={saving}>
              {saving ? <Spinner className="w-4 h-4" /> : <Save size={16} className="mr-1 inline" />}
              Guardar
            </Button>
          </div>
        </div>
      </Card>

      {/* ───── Section 2: Change Password ───── */}
      <Card>
        <SectionHeader icon={Lock} title="Cambiar Contrasena" />

        <div className="space-y-4">
          <Input
            label="Contrasena actual"
            type="password"
            value={currentPassword}
            onChange={e => setCurrentPassword(e.target.value)}
            placeholder="Ingresa tu contrasena actual"
            autoComplete="current-password"
          />

          <div>
            <Input
              label="Nueva contrasena"
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              placeholder="Minimo 8 caracteres"
              autoComplete="new-password"
            />
            <PasswordStrength password={newPassword} />
          </div>

          <Input
            label="Confirmar nueva contrasena"
            type="password"
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
            placeholder="Repite la nueva contrasena"
            autoComplete="new-password"
          />

          <div className="flex justify-end">
            <Button
              onClick={handleChangePassword}
              disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
            >
              {changingPassword ? <Spinner className="w-4 h-4" /> : <Lock size={16} className="mr-1 inline" />}
              Cambiar Contrasena
            </Button>
          </div>
        </div>
      </Card>

      {/* ───── Section 3: Preferences ───── */}
      <Card>
        <SectionHeader icon={Globe} title="Preferencias" />

        <div className="space-y-4">
          <Select
            label="Zona horaria"
            value={timezone}
            onChange={e => setTimezone(e.target.value)}
            options={TIMEZONES}
          />

          <Select
            label="Idioma de la interfaz"
            value={language}
            onChange={e => setLanguage(e.target.value)}
            options={LANGUAGES}
          />

          <div className="flex justify-end">
            <Button onClick={handleSavePrefs} disabled={savingPrefs}>
              {savingPrefs ? <Spinner className="w-4 h-4" /> : <Save size={16} className="mr-1 inline" />}
              Guardar Preferencias
            </Button>
          </div>
        </div>
      </Card>

      {/* ───── Section 4: Help & Support ───── */}
      <Card>
        <SectionHeader icon={HelpCircle} title="Ayuda y Soporte" />

        <div className="space-y-4">
          {/* Links */}
          <div className="flex flex-wrap gap-3">
            <a
              href="https://docs.innotecnia.app"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-bg-secondary border border-border rounded-lg text-sm text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
            >
              <ExternalLink size={14} />
              Documentacion
            </a>
            <a
              href="mailto:soporte@innotecnia.app"
              className="flex items-center gap-2 px-4 py-2 bg-bg-secondary border border-border rounded-lg text-sm text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
            >
              <Mail size={14} />
              soporte@innotecnia.app
            </a>
          </div>

          {/* Version */}
          <p className="text-xs text-text-muted">
            Voice AI Platform v0.2 — Powered by Innotecnia
          </p>

          {/* FAQ */}
          <div>
            <h3 className="text-sm font-medium text-text-secondary mb-3">Preguntas frecuentes</h3>
            <div className="space-y-2">
              {FAQ_ITEMS.map((item, i) => (
                <FaqItem key={i} question={item.q} answer={item.a} />
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
