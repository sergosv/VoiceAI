/**
 * Voice AI — Chat Widget Embeddable
 *
 * Uso:
 *   <script src="https://tu-api.com/chat-widget.js"
 *     data-agent="slug-del-agente"
 *     data-api="https://tu-api.com"
 *     data-position="right"
 *     data-color="#00f0ff"
 *     data-title="Chat con nosotros">
 *   </script>
 */
;(function () {
  'use strict'
  if (window.__voiceai_chat_widget) return
  window.__voiceai_chat_widget = true

  const script = document.currentScript || document.querySelector('script[data-agent]')
  const AGENT = script?.getAttribute('data-agent') || ''
  const API = (script?.getAttribute('data-api') || '').replace(/\/$/, '')
  const POSITION = script?.getAttribute('data-position') || 'right'
  const COLOR = script?.getAttribute('data-color') || '#00f0ff'
  const TITLE = script?.getAttribute('data-title') || ''

  if (!AGENT || !API) {
    console.warn('[VoiceAI Chat] Missing data-agent or data-api')
    return
  }

  // ── State ──
  let config = null
  let conversationId = null
  let isOpen = false
  let isLoading = false
  let messages = [] // { role: 'user'|'agent', text: string }

  // ── Styles ──
  const STYLES = `
    #vai-chat-fab {
      position: fixed; bottom: 20px; ${POSITION}: 20px; z-index: 99998;
      width: 56px; height: 56px; border-radius: 28px;
      background: ${COLOR}; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3); transition: transform 0.2s, box-shadow 0.2s;
    }
    #vai-chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(0,0,0,0.4); }
    #vai-chat-fab svg { width: 26px; height: 26px; fill: #0a0a0f; }
    #vai-chat-fab .vai-badge {
      position: absolute; top: -2px; right: -2px; width: 14px; height: 14px;
      background: #ff4444; border-radius: 50%; border: 2px solid #0a0a0f; display: none;
    }

    #vai-chat-panel {
      position: fixed; bottom: 88px; ${POSITION}: 20px; z-index: 99999;
      width: 380px; max-width: calc(100vw - 32px); height: 520px; max-height: calc(100vh - 120px);
      background: #0f0f17; border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
      display: none; flex-direction: column; overflow: hidden;
      box-shadow: 0 12px 48px rgba(0,0,0,0.5); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      animation: vai-slide-up 0.25s ease-out;
    }
    #vai-chat-panel.vai-open { display: flex; }

    @keyframes vai-slide-up {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .vai-header {
      display: flex; align-items: center; gap: 10px; padding: 14px 16px;
      background: linear-gradient(135deg, ${COLOR}15, ${COLOR}08);
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .vai-header-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: ${COLOR}30; display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0;
    }
    .vai-header-info { flex: 1; min-width: 0; }
    .vai-header-name { color: #f0f0f5; font-size: 14px; font-weight: 600; }
    .vai-header-sub { color: rgba(255,255,255,0.45); font-size: 11px; }
    .vai-header-close {
      background: none; border: none; cursor: pointer; padding: 4px;
      color: rgba(255,255,255,0.4); transition: color 0.15s;
    }
    .vai-header-close:hover { color: #fff; }
    .vai-header-close svg { width: 18px; height: 18px; }

    .vai-messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px;
      scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent;
    }
    .vai-messages::-webkit-scrollbar { width: 4px; }
    .vai-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

    .vai-msg {
      max-width: 82%; padding: 10px 14px; border-radius: 16px;
      font-size: 13.5px; line-height: 1.45; word-wrap: break-word;
      animation: vai-msg-in 0.2s ease-out;
    }
    @keyframes vai-msg-in {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .vai-msg-agent {
      align-self: flex-start; background: rgba(255,255,255,0.06); color: #e0e0ea;
      border-bottom-left-radius: 4px;
    }
    .vai-msg-user {
      align-self: flex-end; background: ${COLOR}; color: #0a0a0f; font-weight: 500;
      border-bottom-right-radius: 4px;
    }

    .vai-typing {
      align-self: flex-start; display: flex; gap: 4px; padding: 12px 16px;
      background: rgba(255,255,255,0.06); border-radius: 16px; border-bottom-left-radius: 4px;
    }
    .vai-typing-dot {
      width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.3);
      animation: vai-bounce 1.2s infinite;
    }
    .vai-typing-dot:nth-child(2) { animation-delay: 0.15s; }
    .vai-typing-dot:nth-child(3) { animation-delay: 0.3s; }
    @keyframes vai-bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-6px); }
    }

    .vai-input-area {
      display: flex; align-items: center; gap: 8px; padding: 12px 14px;
      border-top: 1px solid rgba(255,255,255,0.06); background: rgba(0,0,0,0.2);
    }
    .vai-input {
      flex: 1; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
      border-radius: 22px; padding: 10px 16px; color: #f0f0f5; font-size: 13.5px;
      outline: none; transition: border-color 0.2s;
    }
    .vai-input::placeholder { color: rgba(255,255,255,0.25); }
    .vai-input:focus { border-color: ${COLOR}50; }
    .vai-send-btn {
      width: 36px; height: 36px; border-radius: 50%; background: ${COLOR};
      border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: opacity 0.15s; flex-shrink: 0;
    }
    .vai-send-btn:disabled { opacity: 0.3; cursor: default; }
    .vai-send-btn svg { width: 16px; height: 16px; fill: #0a0a0f; }

    .vai-powered {
      text-align: center; padding: 6px; font-size: 10px; color: rgba(255,255,255,0.2);
    }
    .vai-powered a { color: rgba(255,255,255,0.35); text-decoration: none; }
    .vai-powered a:hover { color: rgba(255,255,255,0.6); }

    @media (max-width: 440px) {
      #vai-chat-panel {
        width: calc(100vw - 16px); bottom: 8px; ${POSITION}: 8px;
        height: calc(100vh - 80px); max-height: none; border-radius: 12px;
      }
      #vai-chat-fab { bottom: 12px; ${POSITION}: 12px; }
    }
  `

  // ── Icons ──
  const ICON_CHAT = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>'
  const ICON_CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
  const ICON_SEND = '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>'
  const ICON_X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'

  // ── Build DOM ──
  const style = document.createElement('style')
  style.textContent = STYLES
  document.head.appendChild(style)

  // FAB
  const fab = document.createElement('button')
  fab.id = 'vai-chat-fab'
  fab.innerHTML = ICON_CHAT + '<span class="vai-badge"></span>'
  fab.setAttribute('aria-label', 'Abrir chat')
  document.body.appendChild(fab)

  // Panel
  const panel = document.createElement('div')
  panel.id = 'vai-chat-panel'
  panel.innerHTML = `
    <div class="vai-header">
      <div class="vai-header-avatar">🤖</div>
      <div class="vai-header-info">
        <div class="vai-header-name" id="vai-agent-name">Cargando...</div>
        <div class="vai-header-sub" id="vai-agent-sub">en linea</div>
      </div>
      <button class="vai-header-close" id="vai-close">${ICON_X}</button>
    </div>
    <div class="vai-messages" id="vai-messages"></div>
    <div class="vai-input-area">
      <input class="vai-input" id="vai-input" placeholder="Escribe un mensaje..." autocomplete="off" />
      <button class="vai-send-btn" id="vai-send" disabled>${ICON_SEND}</button>
    </div>
    <div class="vai-powered">Powered by <a href="https://innotecnia.app" target="_blank" rel="noopener">Voice AI</a></div>
  `
  document.body.appendChild(panel)

  const messagesEl = document.getElementById('vai-messages')
  const inputEl = document.getElementById('vai-input')
  const sendBtn = document.getElementById('vai-send')
  const closeBtn = document.getElementById('vai-close')
  const nameEl = document.getElementById('vai-agent-name')
  const subEl = document.getElementById('vai-agent-sub')

  // ── Helpers ──
  function addMessage(role, text) {
    messages.push({ role, text })
    const div = document.createElement('div')
    div.className = `vai-msg vai-msg-${role}`
    div.textContent = text
    messagesEl.appendChild(div)
    messagesEl.scrollTop = messagesEl.scrollHeight
  }

  function showTyping() {
    const el = document.createElement('div')
    el.className = 'vai-typing'
    el.id = 'vai-typing'
    el.innerHTML = '<div class="vai-typing-dot"></div><div class="vai-typing-dot"></div><div class="vai-typing-dot"></div>'
    messagesEl.appendChild(el)
    messagesEl.scrollTop = messagesEl.scrollHeight
  }

  function hideTyping() {
    const el = document.getElementById('vai-typing')
    if (el) el.remove()
  }

  // ── API calls ──
  async function loadConfig() {
    try {
      const res = await fetch(`${API}/api/widget/config/${AGENT}`)
      if (!res.ok) throw new Error('Agent not found')
      config = await res.json()
      nameEl.textContent = TITLE || config.agent_name || 'Asistente'
      subEl.textContent = config.client_name || 'en linea'
    } catch (e) {
      console.error('[VoiceAI Chat] Config error:', e)
      nameEl.textContent = 'No disponible'
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || isLoading) return
    addMessage('user', text.trim())
    inputEl.value = ''
    sendBtn.disabled = true
    isLoading = true
    showTyping()

    try {
      const res = await fetch(`${API}/api/widget/chat/${AGENT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: text.trim(),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Error')
      }
      const data = await res.json()
      conversationId = data.conversation_id
      hideTyping()
      addMessage('agent', data.text)
    } catch (e) {
      hideTyping()
      addMessage('agent', 'Lo siento, hubo un error. Intenta de nuevo.')
      console.error('[VoiceAI Chat]', e)
    } finally {
      isLoading = false
      sendBtn.disabled = false
      inputEl.focus()
    }
  }

  async function startChat() {
    if (conversationId) return // Ya iniciado
    showTyping()
    try {
      const res = await fetch(`${API}/api/widget/chat/${AGENT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: '' }),
      })
      if (!res.ok) throw new Error('Init failed')
      const data = await res.json()
      conversationId = data.conversation_id
      hideTyping()
      addMessage('agent', data.text)
    } catch (e) {
      hideTyping()
      addMessage('agent', config?.greeting || 'Hola! ¿En qué puedo ayudarte?')
    }
  }

  // ── Events ──
  fab.addEventListener('click', async () => {
    isOpen = !isOpen
    panel.classList.toggle('vai-open', isOpen)
    fab.innerHTML = (isOpen ? ICON_CLOSE : ICON_CHAT) + '<span class="vai-badge"></span>'
    if (isOpen) {
      if (!config) await loadConfig()
      if (!conversationId) await startChat()
      inputEl.focus()
    }
  })

  closeBtn.addEventListener('click', () => {
    isOpen = false
    panel.classList.remove('vai-open')
    fab.innerHTML = ICON_CHAT + '<span class="vai-badge"></span>'
  })

  sendBtn.addEventListener('click', () => sendMessage(inputEl.value))

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(inputEl.value)
    }
  })

  inputEl.addEventListener('input', () => {
    sendBtn.disabled = !inputEl.value.trim() || isLoading
  })

  // ── Preload config ──
  loadConfig()
})()
