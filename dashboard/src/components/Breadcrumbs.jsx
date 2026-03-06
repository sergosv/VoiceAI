import { Link, useLocation, useParams } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'

const ROUTE_LABELS = {
  '': 'Inicio',
  'calls': 'Llamadas',
  'contacts': 'Contactos',
  'appointments': 'Citas',
  'campaigns': 'Campanas',
  'whatsapp': 'WhatsApp',
  'documents': 'Documentos',
  'integrations': 'Integraciones',
  'mcp': 'MCP Servers',
  'api': 'APIs',
  'billing': 'Creditos',
  'settings': 'Agentes',
  'agents': 'Agentes',
  'admin': 'Admin',
  'clients': 'Clientes',
  'new': 'Nuevo',
  'pricing': 'Precios',
  'flow': 'Flow Builder',
}

export function Breadcrumbs() {
  const location = useLocation()
  const params = useParams()

  // No mostrar en pagina de inicio
  if (location.pathname === '/') return null

  const segments = location.pathname.split('/').filter(Boolean)
  if (segments.length === 0) return null

  const crumbs = []
  let path = ''

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i]
    path += `/${seg}`

    // Si es un UUID/ID dinámico, mostrar "Detalle"
    const isId = seg.length > 8 && /[a-f0-9-]/.test(seg)
    const label = isId ? 'Detalle' : (ROUTE_LABELS[seg] || seg)

    const isLast = i === segments.length - 1

    crumbs.push({
      label,
      path,
      isLast,
    })
  }

  return (
    <nav className="flex items-center gap-1.5 text-xs text-text-muted mb-4">
      <Link
        to="/"
        className="hover:text-text-primary transition-colors flex items-center gap-1"
      >
        <Home size={12} />
      </Link>
      {crumbs.map((crumb, i) => (
        <span key={crumb.path} className="flex items-center gap-1.5">
          <ChevronRight size={10} className="text-text-muted/50" />
          {crumb.isLast ? (
            <span className="text-text-secondary font-medium">{crumb.label}</span>
          ) : (
            <Link
              to={crumb.path}
              className="hover:text-text-primary transition-colors"
            >
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
