import React, { useState, useRef, useEffect, useCallback } from 'react'

// ── Simulador de flujo conversacional ─────────────────────────
class FlowSimulator {
  constructor(nodes, edges) {
    this.nodes = new Map(nodes.map(n => [n.id, n]))
    this.edges = edges
    this.state = { currentNodeId: null, variables: {}, history: [], finished: false }
  }

  start() {
    const startNode = [...this.nodes.values()].find(n => n.type === 'start')
    if (!startNode) return [{ type: 'system', text: 'Error: no se encontro nodo de inicio.' }]

    this.state.currentNodeId = startNode.id
    const messages = []

    // Inyectar caller info si esta habilitado
    if (startNode.data.injectCallerInfo) {
      this.state.variables.caller_number = '+525551234567'
      messages.push({ type: 'system', text: 'Variable caller_number = +525551234567' })
    }

    const greeting = startNode.data.greeting || startNode.data.label || 'Inicio'
    messages.push({ type: 'bot', text: this._interpolate(greeting), nodeId: startNode.id })

    // Avanzar automaticamente desde start
    const next = this._getNextNode(startNode.id)
    if (next) {
      this.state.currentNodeId = next.id
      messages.push(...this._processNode(next))
    }

    return messages
  }

  processInput(userText) {
    if (this.state.finished) return []

    const currentNode = this.nodes.get(this.state.currentNodeId)
    if (!currentNode) return [{ type: 'system', text: 'Error: nodo actual no encontrado.' }]

    const messages = [{ type: 'user', text: userText }]

    if (currentNode.type === 'collectInput') {
      const validation = this._validateInput(userText, currentNode.data)
      if (!validation.valid) {
        // Incrementar reintentos
        const retryKey = `__retries_${currentNode.id}`
        const retries = (this.state.variables[retryKey] || 0) + 1
        this.state.variables[retryKey] = retries
        const maxRetries = currentNode.data.maxRetries || 3

        if (retries >= maxRetries) {
          messages.push({ type: 'system', text: `Max reintentos alcanzado (${maxRetries})`, nodeId: currentNode.id })
          const maxRetriesNext = this._getNextNode(currentNode.id, 'maxRetries')
          if (maxRetriesNext) {
            this.state.currentNodeId = maxRetriesNext.id
            messages.push(...this._processNode(maxRetriesNext))
          } else {
            this.state.finished = true
            messages.push({ type: 'system', text: 'Flow terminado (sin ruta maxRetries)' })
          }
        } else {
          const retryMsg = currentNode.data.retryMessage || 'No entendi, puedes repetirlo?'
          messages.push({
            type: 'bot',
            text: this._interpolate(retryMsg) + ` (intento ${retries}/${maxRetries})`,
            nodeId: currentNode.id,
          })
        }
        return messages
      }

      // Input valido: guardar variable
      this.state.variables[currentNode.data.variableName] = validation.value
      messages.push({
        type: 'system',
        text: `Variable ${currentNode.data.variableName} = "${validation.value}"`,
      })

      // Determinar siguiente ruta
      let handleId = 'default'
      if (currentNode.data.variableType === 'confirmation') {
        handleId = this._isAffirmative(userText) ? 'yes' : 'no'
      }

      const next = this._getNextNode(currentNode.id, handleId) || this._getNextNode(currentNode.id)
      if (next) {
        this.state.currentNodeId = next.id
        messages.push(...this._processNode(next))
      } else {
        this.state.finished = true
        messages.push({ type: 'system', text: 'Flow terminado (sin siguiente nodo)' })
      }
    } else if (currentNode.type === 'message' && currentNode.data.waitForResponse) {
      // Mensaje con espera de respuesta: avanzar
      const next = this._getNextNode(currentNode.id)
      if (next) {
        this.state.currentNodeId = next.id
        messages.push(...this._processNode(next))
      } else {
        this.state.finished = true
        messages.push({ type: 'system', text: 'Flow terminado' })
      }
    }

    return messages
  }

  _processNode(node) {
    const messages = []

    switch (node.type) {
      case 'message': {
        const msg = node.data.message || node.data.label || ''
        messages.push({ type: 'bot', text: this._interpolate(msg), nodeId: node.id })
        if (!node.data.waitForResponse) {
          const next = this._getNextNode(node.id)
          if (next) {
            this.state.currentNodeId = next.id
            messages.push(...this._processNode(next))
          }
        }
        break
      }

      case 'collectInput': {
        const prompt = node.data.prompt || node.data.label || ''
        messages.push({ type: 'bot', text: this._interpolate(prompt), nodeId: node.id })
        // Espera input del usuario
        break
      }

      case 'condition': {
        messages.push({
          type: 'system',
          text: `Evaluando condiciones...`,
          nodeId: node.id,
        })
        const result = this._evaluateConditions(node)
        const next = this._getNextNode(node.id, result.handleId)
        if (result.matched) {
          messages.push({ type: 'system', text: `Condicion: ${result.description}` })
        } else {
          messages.push({ type: 'system', text: 'Ruta: default' })
        }
        if (next) {
          this.state.currentNodeId = next.id
          messages.push(...this._processNode(next))
        } else {
          this.state.finished = true
          messages.push({ type: 'system', text: 'Flow terminado (sin ruta desde condicion)' })
        }
        break
      }

      case 'action': {
        const actionType = node.data.actionType || 'desconocida'
        messages.push({
          type: 'action',
          text: `Ejecutando: ${actionType}`,
          nodeId: node.id,
        })
        // Simular resultado
        if (node.data.resultVariable) {
          this.state.variables[node.data.resultVariable] = '(resultado simulado)'
          messages.push({
            type: 'system',
            text: `Variable ${node.data.resultVariable} = "(resultado simulado)"`,
          })
        }
        // Seguir por ruta success
        const next = this._getNextNode(node.id, 'success') || this._getNextNode(node.id)
        if (next) {
          this.state.currentNodeId = next.id
          messages.push(...this._processNode(next))
        } else {
          this.state.finished = true
          messages.push({ type: 'system', text: 'Flow terminado (sin siguiente nodo desde accion)' })
        }
        break
      }

      case 'transfer': {
        const transferMsg = node.data.message || ''
        if (transferMsg) {
          messages.push({ type: 'bot', text: this._interpolate(transferMsg), nodeId: node.id })
        }
        messages.push({
          type: 'transfer',
          text: `Transferir a: ${node.data.transferNumber || '(sin numero)'}`,
          nodeId: node.id,
        })
        this.state.finished = true
        messages.push({ type: 'system', text: 'Flow completado (transferencia)' })
        break
      }

      case 'end': {
        const endMsg = node.data.message || 'Hasta luego.'
        messages.push({ type: 'bot', text: this._interpolate(endMsg), nodeId: node.id })
        this.state.finished = true
        messages.push({ type: 'badge', text: 'Flow completado' })
        break
      }

      case 'wait': {
        const secs = node.data.seconds || 2
        messages.push({
          type: 'system',
          text: `Esperando ${secs} segundo${secs !== 1 ? 's' : ''}...`,
          nodeId: node.id,
        })
        if (node.data.message) {
          messages.push({ type: 'bot', text: this._interpolate(node.data.message), nodeId: node.id })
        }
        const next = this._getNextNode(node.id)
        if (next) {
          this.state.currentNodeId = next.id
          messages.push(...this._processNode(next))
        }
        break
      }

      default:
        messages.push({ type: 'system', text: `Nodo tipo "${node.type}" no soportado en preview` })
    }

    return messages
  }

  _getNextNode(fromNodeId, handleId = null) {
    let edge
    if (handleId) {
      edge = this.edges.find(e => e.source === fromNodeId && e.sourceHandle === handleId)
    }
    if (!edge) {
      edge = this.edges.find(e => e.source === fromNodeId && (!e.sourceHandle || e.sourceHandle === 'default'))
    }
    if (!edge) {
      edge = this.edges.find(e => e.source === fromNodeId)
    }
    return edge ? this.nodes.get(edge.target) : null
  }

  _evaluateConditions(node) {
    const conditions = node.data.conditions || []
    const defaultHandleId = node.data.defaultHandleId || 'default'

    for (const cond of conditions) {
      const varVal = this.state.variables[cond.variable]
      const condVal = cond.value
      let matched = false

      switch (cond.operator) {
        case 'equals':
        case '==':
          matched = String(varVal).toLowerCase() === String(condVal).toLowerCase()
          break
        case 'not_equals':
        case '!=':
          matched = String(varVal).toLowerCase() !== String(condVal).toLowerCase()
          break
        case 'contains':
          matched = String(varVal).toLowerCase().includes(String(condVal).toLowerCase())
          break
        case 'not_contains':
          matched = !String(varVal).toLowerCase().includes(String(condVal).toLowerCase())
          break
        case 'greater_than':
        case '>':
          matched = Number(varVal) > Number(condVal)
          break
        case 'less_than':
        case '<':
          matched = Number(varVal) < Number(condVal)
          break
        case 'exists':
          matched = varVal !== undefined && varVal !== null && varVal !== ''
          break
        case 'not_exists':
          matched = varVal === undefined || varVal === null || varVal === ''
          break
        default:
          matched = String(varVal) === String(condVal)
      }

      if (matched) {
        return {
          matched: true,
          handleId: cond.handleId,
          description: `${cond.variable} ${cond.operator} ${condVal || '""'}`,
        }
      }
    }

    return { matched: false, handleId: defaultHandleId, description: 'default' }
  }

  _validateInput(text, data) {
    const type = data.variableType || 'text'
    const trimmed = text.trim()

    if (!trimmed) return { valid: false }

    switch (type) {
      case 'number': {
        const num = Number(trimmed)
        if (isNaN(num)) return { valid: false }
        return { valid: true, value: num }
      }
      case 'email': {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        if (!emailRegex.test(trimmed)) return { valid: false }
        return { valid: true, value: trimmed }
      }
      case 'phone': {
        const cleaned = trimmed.replace(/[\s\-()]/g, '')
        if (!/^\+?\d{7,15}$/.test(cleaned)) return { valid: false }
        return { valid: true, value: cleaned }
      }
      case 'date': {
        const d = new Date(trimmed)
        if (isNaN(d.getTime())) return { valid: false }
        return { valid: true, value: trimmed }
      }
      case 'confirmation': {
        return { valid: true, value: this._isAffirmative(trimmed) ? 'si' : 'no' }
      }
      case 'text':
      default:
        return { valid: true, value: trimmed }
    }
  }

  _isAffirmative(text) {
    const lower = text.toLowerCase().trim()
    const affirmatives = ['si', 'sí', 'yes', 'ok', 'claro', 'por supuesto', 'afirmativo', 'correcto', 'dale', 'va', 'sale', 'simón', 'simon', 'nel', '1']
    return affirmatives.some(a => lower.includes(a))
  }

  _interpolate(text) {
    return text.replace(/\{\{(\w+)\}\}/g, (_, varName) => {
      const val = this.state.variables[varName]
      return val !== undefined ? String(val) : `{{${varName}}}`
    })
  }

  get currentNodeId() {
    return this.state.currentNodeId
  }

  get variables() {
    // Filtrar variables internas de reintento
    const filtered = {}
    for (const [k, v] of Object.entries(this.state.variables)) {
      if (!k.startsWith('__retries_')) filtered[k] = v
    }
    return filtered
  }

  get isFinished() {
    return this.state.finished
  }
}

// ── Componente FlowPreview ─────────────────────────────────
export function FlowPreview({ nodes, edges, onHighlightNode, onClose }) {
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [simulator, setSimulator] = useState(null)
  const [showVars, setShowVars] = useState(true)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  // Iniciar simulador
  useEffect(() => {
    resetSimulation()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const resetSimulation = useCallback(() => {
    const sim = new FlowSimulator(nodes, edges)
    const initialMessages = sim.start()
    setSimulator(sim)
    setMessages(initialMessages)
    setInputText('')
    if (sim.currentNodeId && onHighlightNode) {
      onHighlightNode(sim.currentNodeId)
    }
  }, [nodes, edges, onHighlightNode])

  const handleSend = useCallback(() => {
    if (!inputText.trim() || !simulator || simulator.isFinished) return

    const newMessages = simulator.processInput(inputText.trim())
    setMessages(prev => [...prev, ...newMessages])
    setInputText('')

    if (simulator.currentNodeId && onHighlightNode) {
      onHighlightNode(simulator.currentNodeId)
    }

    setTimeout(() => inputRef.current?.focus(), 50)
  }, [inputText, simulator, onHighlightNode])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const variables = simulator?.variables || {}

  return (
    <div className="w-96 h-full flex flex-col bg-[#0e0e18] border-l border-[#2a2a3e]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e] shrink-0">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#00f0ff]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-medium text-[#e8e8f0]">Preview del flujo</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowVars(v => !v)}
            className={`p-1.5 rounded text-xs transition-colors ${showVars ? 'text-[#00f0ff] bg-[#00f0ff]/10' : 'text-[#8888a0] hover:text-[#e8e8f0]'}`}
            title="Variables"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          </button>
          <button
            onClick={resetSimulation}
            className="p-1.5 rounded text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
            title="Reiniciar"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
            title="Cerrar preview"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Variables panel */}
      {showVars && Object.keys(variables).length > 0 && (
        <div className="px-3 py-2 border-b border-[#2a2a3e] bg-[#0a0a14] shrink-0">
          <div className="text-[10px] uppercase tracking-wider text-[#555570] mb-1.5">Variables</div>
          <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
            {Object.entries(variables).map(([k, v]) => (
              <div key={k} className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#1a1a2e] border border-[#2a2a3e]">
                <span className="text-[10px] text-[#00f0ff] font-mono">{k}</span>
                <span className="text-[10px] text-[#555570]">=</span>
                <span className="text-[10px] text-[#e8e8f0] font-mono max-w-[120px] truncate">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-3 py-3 border-t border-[#2a2a3e] shrink-0">
        {simulator?.isFinished ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 text-center text-xs text-[#555570]">Simulacion finalizada</div>
            <button
              onClick={resetSimulation}
              className="px-3 py-1.5 text-xs rounded-lg bg-[#00f0ff]/10 text-[#00f0ff] border border-[#00f0ff]/30
                         hover:bg-[#00f0ff]/20 transition-colors"
            >
              Reiniciar
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribe tu respuesta..."
              className="flex-1 px-3 py-2 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]
                         text-[#e8e8f0] placeholder-[#555570] focus:border-[#00f0ff] focus:outline-none"
              autoFocus
            />
            <button
              onClick={handleSend}
              disabled={!inputText.trim()}
              className="p-2 rounded-lg bg-[#00f0ff] text-[#0a0a0f] hover:bg-[#00f0ff]/90
                         transition-colors disabled:opacity-30"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const { type, text } = message

  if (type === 'bot') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] px-3 py-2 rounded-lg rounded-tl-none bg-[#1a1a2e] border border-[#00f0ff]/30">
          <p className="text-sm text-[#e8e8f0] whitespace-pre-wrap">{text}</p>
        </div>
      </div>
    )
  }

  if (type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] px-3 py-2 rounded-lg rounded-tr-none bg-[#252540]">
          <p className="text-sm text-[#e8e8f0] whitespace-pre-wrap">{text}</p>
        </div>
      </div>
    )
  }

  if (type === 'action') {
    return (
      <div className="flex justify-center">
        <div className="px-3 py-1.5 rounded-full bg-[#00f0ff]/5 border border-[#00f0ff]/20">
          <p className="text-xs text-[#00f0ff] italic">
            <span className="mr-1">&#128295;</span>{text}
          </p>
        </div>
      </div>
    )
  }

  if (type === 'transfer') {
    return (
      <div className="flex justify-center">
        <div className="px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20">
          <p className="text-xs text-orange-400 italic">
            <span className="mr-1">&#128222;</span>{text}
          </p>
        </div>
      </div>
    )
  }

  if (type === 'badge') {
    return (
      <div className="flex justify-center">
        <div className="px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/30">
          <p className="text-xs text-green-400 font-medium">{text}</p>
        </div>
      </div>
    )
  }

  // system
  return (
    <div className="flex justify-center">
      <p className="text-[10px] text-[#555570] italic px-2">{text}</p>
    </div>
  )
}
