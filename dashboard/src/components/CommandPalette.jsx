import { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, Phone, UserRound, Calendar, Megaphone,
  MessageCircle, FileText, Plug, CreditCard, Bot, Settings, Users,
  DollarSign, ArrowRight,
} from 'lucide-react'

const COMMANDS = [
  { id: 'home', label: 'Inicio', desc: 'Panel principal', icon: LayoutDashboard, path: '/', keywords: 'dashboard inicio panel' },
  { id: 'calls', label: 'Llamadas', desc: 'Historial de llamadas', icon: Phone, path: '/calls', keywords: 'llamadas calls telefono' },
  { id: 'whatsapp', label: 'WhatsApp', desc: 'Inbox de conversaciones', icon: MessageCircle, path: '/whatsapp', keywords: 'whatsapp mensajes chat' },
  { id: 'campaigns', label: 'Campanas', desc: 'Campanas outbound', icon: Megaphone, path: '/campaigns', keywords: 'campanas campaigns outbound' },
  { id: 'contacts', label: 'Contactos', desc: 'CRM de contactos', icon: UserRound, path: '/contacts', keywords: 'contactos crm clientes' },
  { id: 'appointments', label: 'Citas', desc: 'Calendario de citas', icon: Calendar, path: '/appointments', keywords: 'citas calendario agenda' },
  { id: 'settings', label: 'Agentes', desc: 'Configurar agentes de voz', icon: Bot, path: '/settings', keywords: 'agentes configuracion settings voz prompt' },
  { id: 'documents', label: 'Documentos', desc: 'Base de conocimientos', icon: FileText, path: '/documents', keywords: 'documentos knowledge base archivos' },
  { id: 'integrations', label: 'Integraciones', desc: 'MCP, APIs y herramientas', icon: Plug, path: '/integrations', keywords: 'integraciones mcp api tools' },
  { id: 'mcp', label: 'MCP Servers', desc: 'Servidores MCP configurados', icon: Plug, path: '/integrations/mcp', keywords: 'mcp servers brave search' },
  { id: 'api-integrations', label: 'API Integrations', desc: 'Endpoints HTTP externos', icon: Plug, path: '/integrations/api', keywords: 'api integrations http endpoints' },
  { id: 'billing', label: 'Creditos', desc: 'Balance y transacciones', icon: CreditCard, path: '/billing', keywords: 'creditos billing pagos balance' },
]

const ADMIN_COMMANDS = [
  { id: 'admin-clients', label: 'Clientes (Admin)', desc: 'Gestionar clientes', icon: Users, path: '/admin/clients', keywords: 'admin clientes' },
  { id: 'admin-pricing', label: 'Precios (Admin)', desc: 'Configurar precios', icon: DollarSign, path: '/admin/pricing', keywords: 'admin precios pricing' },
]

export function CommandPalette({ isAdmin = false }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const navigate = useNavigate()

  const allCommands = useMemo(() => {
    return isAdmin ? [...COMMANDS, ...ADMIN_COMMANDS] : COMMANDS
  }, [isAdmin])

  const filtered = useMemo(() => {
    if (!query.trim()) return allCommands
    const q = query.toLowerCase()
    return allCommands.filter(cmd =>
      cmd.label.toLowerCase().includes(q) ||
      cmd.desc.toLowerCase().includes(q) ||
      cmd.keywords.includes(q)
    )
  }, [query, allCommands])

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => !prev)
      }
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return
    const item = listRef.current.children[selectedIndex]
    item?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  function handleSelect(cmd) {
    navigate(cmd.path)
    setOpen(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault()
      handleSelect(filtered[selectedIndex])
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      {/* Palette */}
      <div className="relative w-full max-w-lg mx-4 bg-bg-secondary border border-border rounded-xl shadow-2xl overflow-hidden animate-in">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search size={18} className="text-text-muted shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelectedIndex(0) }}
            onKeyDown={handleKeyDown}
            placeholder="Buscar paginas, acciones..."
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none"
          />
          <kbd className="hidden sm:inline text-[10px] text-text-muted bg-bg-primary px-1.5 py-0.5 rounded border border-border font-mono">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[320px] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-sm text-text-muted">
              Sin resultados para "{query}"
            </div>
          ) : (
            filtered.map((cmd, i) => {
              const Icon = cmd.icon
              return (
                <button
                  key={cmd.id}
                  onClick={() => handleSelect(cmd)}
                  onMouseEnter={() => setSelectedIndex(i)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors cursor-pointer ${
                    i === selectedIndex
                      ? 'bg-accent/10 text-accent'
                      : 'text-text-secondary hover:bg-bg-hover'
                  }`}
                >
                  <Icon size={18} className={i === selectedIndex ? 'text-accent' : 'text-text-muted'} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{cmd.label}</p>
                    <p className="text-xs text-text-muted truncate">{cmd.desc}</p>
                  </div>
                  {i === selectedIndex && (
                    <ArrowRight size={14} className="text-accent shrink-0" />
                  )}
                </button>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-border flex items-center gap-4 text-[10px] text-text-muted">
          <span className="flex items-center gap-1">
            <kbd className="bg-bg-primary px-1 py-0.5 rounded border border-border font-mono">↑↓</kbd>
            Navegar
          </span>
          <span className="flex items-center gap-1">
            <kbd className="bg-bg-primary px-1 py-0.5 rounded border border-border font-mono">↵</kbd>
            Abrir
          </span>
          <span className="flex items-center gap-1">
            <kbd className="bg-bg-primary px-1 py-0.5 rounded border border-border font-mono">Esc</kbd>
            Cerrar
          </span>
        </div>
      </div>
    </div>
  )
}
