import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

export function ClientSelector({ value, onChange }) {
  const { user } = useAuth()
  const [clients, setClients] = useState([])

  useEffect(() => {
    if (user?.role !== 'admin') return
    let cancelled = false
    api.get('/clients')
      .then(data => { if (!cancelled) setClients(data) })
      .catch(() => {}) // selector falla silenciosamente — no bloquea UI
    return () => { cancelled = true }
  }, [user])

  // Solo mostrar para admin
  if (user?.role !== 'admin') return null

  return (
    <select
      value={value || ''}
      onChange={e => onChange(e.target.value || null)}
      className="bg-bg-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
    >
      <option value="">Todos los clientes</option>
      {clients.map(c => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  )
}
