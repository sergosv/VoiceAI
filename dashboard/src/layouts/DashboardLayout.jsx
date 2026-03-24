import { Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Sidebar } from '../components/Sidebar'
import { Breadcrumbs } from '../components/Breadcrumbs'
import { CommandPalette } from '../components/CommandPalette'
import { LowBalanceAlert } from '../components/LowBalanceAlert'
import { PageLoader } from '../components/ui/Spinner'
import { Search, X, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export function DashboardLayout() {
  const { user, loading, impersonatingClientId, impersonatingClientName, stopImpersonation } = useAuth()
  const navigate = useNavigate()

  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />

  const isAdmin = user?.role === 'admin'

  return (
    <div className="min-h-screen bg-bg-primary">
      <Sidebar />
      <CommandPalette isAdmin={isAdmin} />

      {/* Impersonation banner */}
      {impersonatingClientId && (
        <div className="fixed top-0 left-0 right-0 z-[60] bg-amber-500/90 backdrop-blur-sm text-black text-sm font-medium flex items-center justify-center gap-3 h-10 px-4">
          <span>
            Viendo como: <strong>{impersonatingClientName}</strong>
          </span>
          <button
            onClick={() => { navigate('/admin/clients'); stopImpersonation(); }}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-black/15 hover:bg-black/25 transition-colors text-xs font-medium cursor-pointer"
          >
            <ArrowLeft size={12} /> Panel Admin
          </button>
          <button
            onClick={() => { stopImpersonation(); navigate('/'); }}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-black/15 hover:bg-black/25 transition-colors text-xs font-medium cursor-pointer"
          >
            <X size={12} /> Salir
          </button>
        </div>
      )}

      {/* Top bar for mobile — includes search trigger */}
      <div className={`lg:hidden fixed ${impersonatingClientId ? 'top-10' : 'top-0'} right-0 left-0 z-30 h-12 bg-bg-secondary/80 backdrop-blur-md border-b border-border flex items-center justify-end px-4`}>
        <button
          onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-primary border border-border text-text-muted text-xs hover:border-accent/50 transition-colors cursor-pointer"
        >
          <Search size={12} />
          Buscar...
        </button>
      </div>

      <main className={`lg:ml-60 p-4 pt-14 lg:p-6 lg:pt-6 ${impersonatingClientId ? 'mt-10' : ''}`}>
        {/* Search shortcut hint — desktop only */}
        <div className="hidden lg:flex justify-end mb-2 -mt-1">
          <button
            onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-text-muted text-xs hover:border-accent/50 hover:text-text-secondary transition-colors cursor-pointer"
          >
            <Search size={12} />
            Buscar...
            <kbd className="text-[10px] bg-bg-secondary px-1.5 py-0.5 rounded border border-border font-mono ml-1">
              Ctrl+K
            </kbd>
          </button>
        </div>

        {(!isAdmin || impersonatingClientId) && <LowBalanceAlert />}
        <Breadcrumbs />
        <Outlet />
      </main>
    </div>
  )
}
