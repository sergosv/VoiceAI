import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL || '/api'

async function getToken() {
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token || null
}

async function request(path, options = {}) {
  const token = await getToken()
  const headers = { ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    await supabase.auth.signOut()
    window.location.href = '/login'
    throw new Error('Sesión expirada')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error del servidor' }))
    throw new Error(err.detail || `Error ${res.status}`)
  }

  return res.json()
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
  patch: (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (path) => request(path, { method: 'DELETE' }),
  upload: (path, formData) => request(path, { method: 'POST', body: formData }),
}
