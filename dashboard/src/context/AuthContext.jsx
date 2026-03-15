import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [impersonatingClientId, setImpersonatingClientId] = useState(() => sessionStorage.getItem('impersonateClientId'))
  const [impersonatingClientName, setImpersonatingClientName] = useState(() => sessionStorage.getItem('impersonateClientName'))

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) fetchUser()
      else setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) fetchUser()
      else {
        setUser(null)
        setLoading(false)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  async function fetchUser() {
    try {
      const data = await api.get('/auth/me')
      setUser(data)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  async function signIn(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function signOut() {
    stopImpersonation()
    await supabase.auth.signOut()
    setUser(null)
    setSession(null)
  }

  function startImpersonation(clientId, clientName) {
    sessionStorage.setItem('impersonateClientId', clientId)
    sessionStorage.setItem('impersonateClientName', clientName)
    setImpersonatingClientId(clientId)
    setImpersonatingClientName(clientName)
  }

  function stopImpersonation() {
    sessionStorage.removeItem('impersonateClientId')
    sessionStorage.removeItem('impersonateClientName')
    setImpersonatingClientId(null)
    setImpersonatingClientName(null)
  }

  return (
    <AuthContext.Provider value={{
      session, user, loading, signIn, signOut,
      impersonatingClientId, impersonatingClientName,
      startImpersonation, stopImpersonation,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
