import { Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { PageLoader } from '../components/ui/Spinner'
import { Radio } from 'lucide-react'

export function AuthLayout() {
  const { user, loading } = useAuth()

  if (loading) return <PageLoader />
  if (user) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Radio size={28} className="text-accent" />
          <span className="text-xl font-bold">Voice AI Platform</span>
        </div>
        <Outlet />
      </div>
    </div>
  )
}
