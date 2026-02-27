import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export function ForgotPassword() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/login`,
      })
      if (err) throw err
      setSent(true)
    } catch (err) {
      setError(err.message || 'Error enviando email')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <Card>
        <h2 className="text-lg font-semibold mb-2">Revisa tu email</h2>
        <p className="text-text-secondary text-sm mb-4">
          Enviamos un enlace de recuperación a <strong>{email}</strong>.
        </p>
        <Button variant="secondary" onClick={() => navigate('/login')} className="w-full">
          Volver al login
        </Button>
      </Card>
    )
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold mb-4">Recuperar contraseña</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          placeholder="tu@email.com"
          required
        />
        {error && <p className="text-danger text-sm">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? 'Enviando...' : 'Enviar enlace'}
        </Button>
        <button
          type="button"
          onClick={() => navigate('/login')}
          className="text-sm text-accent hover:underline w-full text-center cursor-pointer"
        >
          Volver al login
        </button>
      </form>
    </Card>
  )
}
