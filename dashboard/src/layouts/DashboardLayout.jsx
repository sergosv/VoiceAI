import { Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Sidebar } from '../components/Sidebar'
import { PageLoader } from '../components/ui/Spinner'

export function DashboardLayout() {
  const { user, loading } = useAuth()

  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="min-h-screen bg-bg-primary">
      <Sidebar />
      <main className="lg:ml-60 p-4 pt-14 lg:p-6 lg:pt-6">
        <Outlet />
      </main>
    </div>
  )
}
