import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MessageSquare, Search, Send, Globe, Mail, Smartphone, Camera, User } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return 'ahora'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}d`
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
}

const CHANNEL_CONFIG = {
  whatsapp: { icon: MessageSquare, label: 'WhatsApp', color: 'text-green-400', bg: 'bg-green-500/20' },
  sms: { icon: Smartphone, label: 'SMS', color: 'text-blue-400', bg: 'bg-blue-500/20' },
  SMS: { icon: Smartphone, label: 'SMS', color: 'text-blue-400', bg: 'bg-blue-500/20' },
  webchat: { icon: Globe, label: 'WebChat', color: 'text-purple-400', bg: 'bg-purple-500/20' },
  Live_Chat: { icon: Globe, label: 'WebChat', color: 'text-purple-400', bg: 'bg-purple-500/20' },
  facebook: { icon: MessageSquare, label: 'Facebook', color: 'text-blue-400', bg: 'bg-blue-500/20' },
  FB: { icon: MessageSquare, label: 'Facebook', color: 'text-blue-400', bg: 'bg-blue-500/20' },
  instagram: { icon: Camera, label: 'Instagram', color: 'text-pink-400', bg: 'bg-pink-500/20' },
  IG: { icon: Camera, label: 'Instagram', color: 'text-pink-400', bg: 'bg-pink-500/20' },
  email: { icon: Mail, label: 'Email', color: 'text-gray-400', bg: 'bg-gray-500/20' },
  Email: { icon: Mail, label: 'Email', color: 'text-gray-400', bg: 'bg-gray-500/20' },
}
const DEFAULT_CHANNEL = { icon: MessageSquare, label: 'Chat', color: 'text-text-muted', bg: 'bg-bg-hover' }

function ChannelBadge({ channel }) {
  const cfg = CHANNEL_CONFIG[channel] || DEFAULT_CHANNEL
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
      <Icon size={10} />
      {cfg.label}
    </span>
  )
}

export function GHLInbox() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('id')

  const [conversations, setConversations] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [stats, setStats] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sendText, setSendText] = useState('')
  const [sending, setSending] = useState(false)

  const messagesEndRef = useRef(null)

  useEffect(() => {
    loadConversations()
    loadStats()
  }, [statusFilter])

  useEffect(() => {
    if (selectedId) loadMessages(selectedId)
  }, [selectedId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function loadConversations() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      const url = `/ghl/conversations${params.toString() ? '?' + params : ''}`
      const data = await api.get(url)
      setConversations(data || [])
    } catch (err) {
      console.error('Error cargando conversaciones GHL:', err)
    } finally {
      setLoading(false)
    }
  }

  async function loadMessages(convId) {
    setLoadingMessages(true)
    try {
      const data = await api.get(`/ghl/conversations/${convId}/messages`)
      setMessages(data || [])
    } catch {
      toast.error('Error cargando mensajes')
    } finally {
      setLoadingMessages(false)
    }
  }

  async function loadStats() {
    try {
      const data = await api.get('/ghl/stats')
      setStats(data)
    } catch { /* stats son no-criticos */ }
  }

  async function handleSend(e) {
    e.preventDefault()
    if (!sendText.trim() || !selectedId) return
    setSending(true)
    try {
      await api.post(`/ghl/conversations/${selectedId}/send`, { message: sendText })
      setSendText('')
      await loadMessages(selectedId)
    } catch (err) {
      toast.error(err.message || 'Error enviando mensaje')
    } finally {
      setSending(false)
    }
  }

  function selectConversation(id) {
    setSearchParams({ id })
  }

  const filteredConvs = conversations.filter(c => {
    if (!search) return true
    const s = search.toLowerCase()
    return (
      c.remote_phone?.toLowerCase().includes(s) ||
      c.contact_name?.toLowerCase().includes(s) ||
      c.agent_name?.toLowerCase().includes(s)
    )
  })

  const selectedConv = conversations.find(c => c.id === selectedId)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe size={24} className="text-purple-400" />
          <h1 className="text-2xl font-bold">GoHighLevel Inbox</h1>
        </div>
        {stats && (
          <div className="flex gap-4 text-sm">
            <div className="text-center">
              <p className="text-lg font-bold text-accent">{stats.active_conversations}</p>
              <p className="text-[10px] text-text-muted">Activas</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{stats.messages_today}</p>
              <p className="text-[10px] text-text-muted">Msgs hoy</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{stats.total_conversations}</p>
              <p className="text-[10px] text-text-muted">Total</p>
            </div>
          </div>
        )}
      </div>

      {/* Main 2-panel layout */}
      <div className="flex gap-4 h-[calc(100vh-200px)]">
        {/* Left: Conversation list */}
        <Card className="w-80 flex-shrink-0 flex flex-col overflow-hidden !p-0">
          {/* Search + filter */}
          <div className="p-3 border-b border-border space-y-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Buscar por telefono, contacto, agente..."
                className="w-full bg-bg-primary border border-border rounded-lg pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex gap-1">
              {['', 'active', 'closed', 'expired'].map(s => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${
                    statusFilter === s
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-border text-text-muted hover:text-text-primary'
                  }`}
                >
                  {s || 'Todas'}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Spinner size={20} />
              </div>
            ) : filteredConvs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                <Globe size={32} className="text-text-muted mb-3 opacity-30" />
                <p className="text-sm text-text-muted">
                  {search ? `Sin resultados para "${search}"` : 'Sin conversaciones'}
                </p>
                {!search && (
                  <p className="text-xs text-text-muted mt-1">Las conversaciones apareceran cuando recibas mensajes via GoHighLevel</p>
                )}
              </div>
            ) : (
              filteredConvs.map(conv => (
                <button
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={`w-full text-left px-3 py-3 border-b border-border/50 hover:bg-bg-hover transition-colors ${
                    selectedId === conv.id ? 'bg-accent/5 border-l-2 border-l-accent' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium truncate">
                      {conv.contact_name || conv.remote_phone || 'Visitante'}
                    </span>
                    <span className="text-[10px] text-text-muted">{timeAgo(conv.last_message_at)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-xs text-text-muted truncate">
                      {conv.agent_name && <span className="text-accent">{conv.agent_name}</span>}
                      {conv.agent_name && conv.remote_phone && ' · '}
                      {conv.remote_phone ? `+${conv.remote_phone}` : ''}
                    </span>
                    <div className="flex items-center gap-1">
                      <ChannelBadge channel={conv.channel} />
                      <span className={`text-[10px] px-1 py-0.5 rounded ${
                        conv.status === 'active' ? 'bg-green-500/20 text-green-400' :
                        conv.status === 'closed' ? 'bg-red-500/20 text-red-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {conv.status}
                      </span>
                    </div>
                  </div>
                  <p className="text-[10px] text-text-muted mt-0.5">
                    {conv.message_count} msgs
                  </p>
                </button>
              ))
            )}
          </div>
        </Card>

        {/* Right: Messages */}
        <Card className="flex-1 flex flex-col overflow-hidden !p-0">
          {!selectedId ? (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              <div className="text-center">
                <Globe size={48} className="mx-auto mb-3 opacity-20" />
                <p className="text-sm">Selecciona una conversacion</p>
              </div>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                    <User size={16} className="text-purple-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium flex items-center gap-2">
                      {selectedConv?.contact_name || selectedConv?.remote_phone || 'Visitante'}
                      <ChannelBadge channel={selectedConv?.channel} />
                    </p>
                    <p className="text-[10px] text-text-muted">
                      {selectedConv?.agent_name && `${selectedConv.agent_name} · `}
                      {selectedConv?.remote_phone ? `+${selectedConv.remote_phone}` : 'Sin telefono'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] px-2 py-1 rounded ${
                    selectedConv?.status === 'active' ? 'bg-green-500/20 text-green-400' :
                    selectedConv?.status === 'closed' ? 'bg-red-500/20 text-red-400' :
                    'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {selectedConv?.status}
                  </span>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {loadingMessages ? (
                  <div className="flex items-center justify-center py-8">
                    <Spinner size={20} />
                  </div>
                ) : messages.length === 0 ? (
                  <p className="text-sm text-text-muted text-center py-8">Sin mensajes</p>
                ) : (
                  messages.map(msg => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[70%] px-3 py-2 rounded-xl text-sm ${
                          msg.direction === 'outbound'
                            ? 'bg-purple-600/20 text-text-primary rounded-br-sm'
                            : 'bg-bg-secondary text-text-primary rounded-bl-sm'
                        }`}
                      >
                        {msg.channel && (
                          <div className="mb-1">
                            <ChannelBadge channel={msg.channel} />
                          </div>
                        )}
                        <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                        {msg.tool_calls?.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {msg.tool_calls.map((tc, i) => (
                              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent">
                                {tc.name}
                              </span>
                            ))}
                          </div>
                        )}
                        <p className="text-[10px] text-text-muted mt-1 text-right">
                          {formatTime(msg.created_at)}
                        </p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Send input */}
              {selectedConv?.status === 'active' && (
                <form onSubmit={handleSend} className="px-4 py-3 border-t border-border flex gap-2">
                  <input
                    value={sendText}
                    onChange={e => setSendText(e.target.value)}
                    placeholder="Escribe un mensaje..."
                    className="flex-1 bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent"
                    disabled={sending}
                  />
                  <Button type="submit" disabled={sending || !sendText.trim()}>
                    <Send size={16} />
                  </Button>
                </form>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
