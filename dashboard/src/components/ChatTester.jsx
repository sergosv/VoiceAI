import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { MessageSquare, Send, RotateCcw, Copy, X, Bot, User, Wrench } from 'lucide-react'
import { api } from '../lib/api'
import { Button } from './ui/Button'
import { Input } from './ui/Input'

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-3 py-2">
      <Bot size={14} className="text-accent" />
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 bg-accent/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 bg-accent/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1.5 h-1.5 bg-accent/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  )
}

function ToolBadge({ tool }) {
  return (
    <div className="flex items-start gap-2 px-3 py-1.5 mx-8 my-1 rounded-lg bg-purple-500/10 border border-purple-500/20 text-xs">
      <Wrench size={12} className="text-purple-400 mt-0.5 shrink-0" />
      <div className="min-w-0">
        <span className="text-purple-400 font-medium">{tool.name}</span>
        {tool.args && Object.keys(tool.args).length > 0 && (
          <span className="text-purple-400/70 ml-1">
            ({Object.entries(tool.args).map(([k, v]) => `${k}: ${typeof v === 'string' && v.length > 40 ? v.slice(0, 40) + '...' : v}`).join(', ')})
          </span>
        )}
        {tool.result && (
          <p className="text-purple-300/60 mt-0.5 line-clamp-2">{tool.result}</p>
        )}
      </div>
    </div>
  )
}

function ChatBubble({ role, text }) {
  const isAgent = role === 'agent'
  return (
    <div className={`flex gap-2 ${isAgent ? '' : 'flex-row-reverse'}`}>
      <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
        isAgent ? 'bg-accent/20' : 'bg-bg-tertiary'
      }`}>
        {isAgent ? <Bot size={12} className="text-accent" /> : <User size={12} className="text-text-muted" />}
      </div>
      <div className={`max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed ${
        isAgent
          ? 'bg-bg-tertiary text-text-primary rounded-bl-sm'
          : 'bg-accent/20 text-text-primary rounded-br-sm'
      }`}>
        {text}
      </div>
    </div>
  )
}

function ChatTesterContent({ agentId, agentName, agentType, campaignScript, flowOverride, onClose }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [turnCount, setTurnCount] = useState(0)
  const [started, setStarted] = useState(false)
  const [contactName, setContactName] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const isOutbound = agentType === 'outbound' || agentType === 'both'
  const needsContactName = isOutbound && !started

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Auto-iniciar para inbound
  useEffect(() => {
    if (!isOutbound) {
      startChat()
    }
  }, [])

  async function startChat(name) {
    setStarted(true)
    setLoading(true)
    try {
      if (campaignScript && name) {
        // Outbound con script: el contacto contesta "Bueno?"
        // Primero crear la conversación sin mensaje
        const initBody = {
          message: '',
          contact_name: name,
          campaign_script: campaignScript,
        }
        if (flowOverride) initBody.flow_override = flowOverride
        const init = await api.post(`/agents/${agentId}/chat`, initBody)
        setConversationId(init.conversation_id)
        // Luego enviar "Bueno?" como el contacto contestando
        const res = await api.post(`/agents/${agentId}/chat`, {
          conversation_id: init.conversation_id,
          message: 'Bueno?',
        })
        setMessages([
          { role: 'user', text: 'Bueno?' },
          { role: 'agent', text: res.text, tools: res.tool_calls },
        ])
        setTurnCount(1)
      } else {
        // Inbound: el agente saluda primero
        const body = { message: '__greeting__' }
        if (name) body.contact_name = name
        if (flowOverride) body.flow_override = flowOverride
        const res = await api.post(`/agents/${agentId}/chat`, body)
        setConversationId(res.conversation_id)
        setMessages([{ role: 'agent', text: res.text, tools: res.tool_calls }])
        setTurnCount(1)
      }
      setTimeout(() => inputRef.current?.focus(), 100)
    } catch (err) {
      setMessages([{ role: 'agent', text: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  async function handleSend() {
    const msg = input.trim()
    if (!msg || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: msg }])
    setLoading(true)

    try {
      const res = await api.post(`/agents/${agentId}/chat`, {
        conversation_id: conversationId,
        message: msg,
      })
      setConversationId(res.conversation_id)
      setMessages(prev => [...prev, { role: 'agent', text: res.text, tools: res.tool_calls }])
      setTurnCount(t => t + 1)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'agent', text: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  async function handleReset() {
    if (conversationId) {
      try {
        await api.delete(`/agents/${agentId}/chat/${conversationId}`)
      } catch { /* ignore */ }
    }
    setMessages([])
    setConversationId(null)
    setTurnCount(0)
    setStarted(false)
    setContactName('')
    if (!isOutbound) {
      startChat()
    }
  }

  function handleCopy() {
    const text = messages
      .map(m => `${m.role === 'agent' ? 'Agente' : 'Usuario'}: ${m.text}`)
      .join('\n')
    navigator.clipboard.writeText(text)
  }

  function handleOutboundStart() {
    startChat(contactName || 'Contacto')
  }

  // Pantalla de nombre de contacto para outbound
  if (needsContactName) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
        <Bot size={32} className="text-accent" />
        <h3 className="text-lg font-semibold">Probar llamada saliente</h3>
        <p className="text-sm text-text-muted text-center max-w-xs">
          Simula una llamada outbound. El agente iniciara la conversacion presentandose al contacto.
        </p>
        <form onSubmit={e => { e.preventDefault(); e.stopPropagation(); handleOutboundStart() }} className="w-full max-w-xs space-y-3">
          <Input
            label="Nombre del contacto"
            value={contactName}
            onChange={e => setContactName(e.target.value)}
            placeholder="Ej: Juan Perez"
            autoFocus
          />
          <Button type="submit" className="w-full">
            Iniciar conversacion
          </Button>
        </form>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-accent" />
          <span className="text-sm font-medium">{agentName}</span>
          <span className="text-[10px] text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
            {turnCount}/50 turnos
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="p-1.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            title="Copiar conversacion"
          >
            <Copy size={14} />
          </button>
          <button
            onClick={handleReset}
            className="p-1.5 text-text-muted hover:text-warning transition-colors cursor-pointer"
            title="Reiniciar"
          >
            <RotateCcw size={14} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            title="Cerrar"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {messages.map((msg, i) => (
          <div key={i}>
            {/* Tool badges antes del mensaje del agente */}
            {msg.role === 'agent' && msg.tools?.length > 0 && (
              <div className="space-y-1 mb-2">
                {msg.tools.map((tool, j) => (
                  <ToolBadge key={j} tool={tool} />
                ))}
              </div>
            )}
            <ChatBubble role={msg.role} text={msg.text} />
          </div>
        ))}
        {loading && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={e => { e.preventDefault(); e.stopPropagation(); handleSend() }} className="shrink-0 px-4 py-3 border-t border-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Escribe un mensaje..."
            disabled={loading}
            className="flex-1 bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-3 py-2 bg-accent text-bg-primary rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}

export function ChatTester({ open, onClose, agentId, agentName, agentType, campaignScript, flowOverride }) {
  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-lg h-[600px] max-h-[80vh] bg-bg-secondary border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        <ChatTesterContent
          agentId={agentId}
          agentName={agentName}
          agentType={agentType}
          campaignScript={campaignScript}
          flowOverride={flowOverride}
          onClose={onClose}
        />
      </div>
    </div>,
    document.body,
  )
}

export function ChatTesterButton({ agentId, agentName, agentType = 'inbound', campaignScript, flowOverride, label }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button variant="secondary" type="button" onClick={() => setOpen(true)}>
        <MessageSquare size={16} className="mr-1.5 inline" />
        {label || 'Probar agente'}
      </Button>
      <ChatTester
        open={open}
        onClose={() => setOpen(false)}
        agentId={agentId}
        agentName={agentName}
        agentType={agentType}
        campaignScript={campaignScript}
        flowOverride={flowOverride}
      />
    </>
  )
}
