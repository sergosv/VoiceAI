import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  LayoutDashboard, Phone, FileText, Settings, Users, CreditCard, DollarSign,
  LogOut, Radio, Menu, X, UserRound, Calendar, Megaphone, Plug, MessageCircle,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calls', icon: Phone, label: 'Llamadas' },
  { to: '/contacts', icon: UserRound, label: 'Contactos' },
  { to: '/appointments', icon: Calendar, label: 'Citas' },
  { to: '/campaigns', icon: Megaphone, label: 'Campañas' },
  { to: '/whatsapp', icon: MessageCircle, label: 'WhatsApp' },
  { to: '/documents', icon: FileText, label: 'Documentos' },
  { to: '/integrations', icon: Plug, label: 'Integraciones' },
  { to: '/billing', icon: CreditCard, label: 'Créditos' },
  { to: '/settings', icon: Settings, label: 'Configuración' },
]

const adminItems = [
  { to: '/admin/clients', icon: Users, label: 'Clientes' },
  { to: '/admin/pricing', icon: DollarSign, label: 'Precios' },
]

function NavItem({ to, icon: Icon, label, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
          isActive
            ? 'bg-accent/10 text-accent'
            : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
        }`
      }
    >
      <Icon size={18} />
      {label}
    </NavLink>
  )
}

export function Sidebar() {
  const { user, signOut } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [open, setOpen] = useState(false)

  function closeMobile() {
    setOpen(false)
  }

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setOpen(true)}
        className="fixed top-3 left-3 z-50 lg:hidden p-2 rounded-lg bg-bg-secondary border border-border text-text-primary cursor-pointer"
        aria-label="Abrir menú"
      >
        <Menu size={20} />
      </button>

      {/* Overlay */}
      {open && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={closeMobile} />
      )}

      {/* Sidebar */}
      <aside className={`
        w-60 h-screen bg-bg-secondary border-r border-border flex flex-col fixed left-0 top-0 z-50
        transition-transform duration-200
        lg:translate-x-0
        ${open ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Radio size={20} className="text-accent" />
          <span className="font-bold text-sm">Voice AI</span>
          <span className="text-xs text-text-muted ml-auto hidden lg:inline">v0.2</span>
          <button
            onClick={closeMobile}
            className="lg:hidden text-text-muted hover:text-text-primary cursor-pointer ml-auto"
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(item => (
            <NavItem key={item.to} {...item} end={item.to === '/'} onClick={closeMobile} />
          ))}

          {isAdmin && (
            <>
              <div className="pt-4 pb-1 px-3">
                <p className="text-xs text-text-muted uppercase tracking-wider">Admin</p>
              </div>
              {adminItems.map(item => (
                <NavItem key={item.to} {...item} onClick={closeMobile} />
              ))}
            </>
          )}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center text-xs font-bold text-accent">
              {user?.email?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs truncate">{user?.email}</p>
              <p className="text-xs text-text-muted">{user?.role}</p>
            </div>
            <button onClick={signOut} className="text-text-muted hover:text-danger cursor-pointer" title="Cerrar sesión">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
