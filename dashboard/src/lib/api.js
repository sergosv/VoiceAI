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
  const impersonateId = sessionStorage.getItem('impersonateClientId')
  if (impersonateId) headers['X-Impersonate-Client'] = impersonateId

  const { signal, ...rest } = options
  const res = await fetch(`${BASE}${path}`, { ...rest, headers, signal })

  if (res.status === 401) {
    await supabase.auth.signOut()
    window.location.href = '/login'
    throw new Error('Sesión expirada')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error del servidor' }))
    throw new Error(err.detail || `Error ${res.status}`)
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') return null
  return res.json()
}

async function downloadFile(path) {
  const token = await getToken()
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const impersonateId = sessionStorage.getItem('impersonateClientId')
  if (impersonateId) headers['X-Impersonate-Client'] = impersonateId
  const res = await fetch(`${BASE}${path}`, { headers })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename=(.+)/)
  const filename = match ? match[1] : 'export.csv'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const api = {
  get: (path, { signal } = {}) => request(path, { signal }),
  post: (path, data, { signal } = {}) => request(path, { method: 'POST', body: JSON.stringify(data), signal }),
  patch: (path, data, { signal } = {}) => request(path, { method: 'PATCH', body: JSON.stringify(data), signal }),
  delete: (path, { signal } = {}) => request(path, { method: 'DELETE', signal }),
  upload: (path, formData, { signal } = {}) => request(path, { method: 'POST', body: formData, signal }),
  download: (path) => downloadFile(path),
}
