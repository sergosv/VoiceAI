import { Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Sidebar } from '../components/Sidebar'
import { Breadcrumbs } from '../components/Breadcrumbs'
import { CommandPalette } from '../components/CommandPalette'
import { PageLoader } from '../components/ui/Spinner'
import { Search } from 'lucide-react'

export function DashboardLayout() {
  const { user, loading } = useAuth()

  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />

  const isAdmin = user?.role === 'admin'

  return (
    <div className="min-h-screen bg-bg-primary">
      <Sidebar />
      <CommandPalette isAdmin={isAdmin} />

      {/* Top bar for mobile — includes search trigger */}
      <div className="lg:hidden fixed top-0 right-0 left-0 z-30 h-12 bg-bg-secondary/80 backdrop-blur-md border-b border-border flex items-center justify-end px-4">
        <button
          onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-primary border border-border text-text-muted text-xs hover:border-accent/50 transition-colors cursor-pointer"
        >
          <Search size={12} />
          Buscar...
        </button>
      </div>

      <main className="lg:ml-60 p-4 pt-14 lg:p-6 lg:pt-6">
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

        <Breadcrumbs />
        <Outlet />
      </main>
    </div>
  )
}
