/**
 * Voice AI Widget — Unified embeddable voice + chat agent for websites.
 *
 * Usage:
 *   <script src="https://your-api.com/widget.js"
 *           data-agent="your-agent-slug"
 *           data-api="https://your-api.com/api"></script>
 *
 * Options (data attributes):
 *   data-agent    — Agent slug (required)
 *   data-api      — API base URL (required)
 *   data-position — "bottom-right" (default), "bottom-left"
 *   data-color    — Accent color (default: "#00f0ff")
 *   data-title    — Button tooltip text
 */
(function () {
  'use strict';

  if (window.__voiceAIWidget) return;
  window.__voiceAIWidget = true;

  const script = document.currentScript;
  const AGENT_SLUG = script?.getAttribute('data-agent');
  const API_BASE = script?.getAttribute('data-api') || '/api';
  const POSITION = script?.getAttribute('data-position') || 'bottom-right';
  const POS_SIDE = POSITION === 'bottom-left' ? 'left' : 'right';
  const ACCENT = script?.getAttribute('data-color') || '#00f0ff';
  const TITLE = script?.getAttribute('data-title') || 'Hablar con asistente';

  if (!AGENT_SLUG) {
    console.error('[VoiceAI Widget] Missing data-agent attribute');
    return;
  }

  // ── State ──
  let mode = null; // null | 'voice' | 'chat'
  let voiceState = 'idle'; // idle | connecting | active | error
  let room = null;
  let config = null;
  let channels = ['voice'];
  // Chat state
  let conversationId = null;
  let chatOpen = false;
  let chatLoading = false;
  let chatMessages = [];

  // ── Icons ──
  const ICON_MIC = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>';
  const ICON_STOP = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
  const ICON_CHAT = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
  const ICON_CLOSE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  const ICON_SEND = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  const ICON_HEADSET = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>';
  const ICON_KEYBOARD = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/></svg>';

  // ── Styles ──
  const css = `
    .vai-fab {
      position: fixed; ${POS_SIDE}: 24px; bottom: 24px;
      width: 60px; height: 60px; border-radius: 50%;
      background: ${ACCENT}; color: #0a0a0f; border: none; cursor: pointer;
      box-shadow: 0 4px 20px ${ACCENT}40;
      display: flex; align-items: center; justify-content: center;
      z-index: 99999; transition: transform 0.2s, box-shadow 0.2s;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .vai-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px ${ACCENT}60; }
    .vai-fab.active { background: #ef4444; box-shadow: 0 4px 20px #ef444440; animation: vai-pulse 1.5s infinite; }
    .vai-fab.connecting { cursor: wait; animation: vai-connecting 1.2s ease-in-out infinite; }
    @keyframes vai-connecting {
      0%, 100% { transform: scale(1); opacity: 0.7; }
      50% { transform: scale(1.1); opacity: 1; }
    }
    @keyframes vai-pulse {
      0%, 100% { box-shadow: 0 0 0 0 #ef444440; }
      50% { box-shadow: 0 0 0 12px #ef444400; }
    }

    .vai-tooltip {
      position: fixed; ${POS_SIDE}: 92px; bottom: 38px;
      background: #1a1a2e; color: #fff; padding: 8px 14px; border-radius: 8px;
      font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      white-space: nowrap; z-index: 99998; opacity: 0; transition: opacity 0.2s;
      pointer-events: none; border: 1px solid rgba(255,255,255,0.1);
    }
    .vai-fab:hover + .vai-tooltip { opacity: 1; }

    /* ── Mode selector popup ── */
    .vai-mode-menu {
      position: fixed; ${POS_SIDE}: 24px; bottom: 92px;
      background: #12121e; border: 1px solid rgba(255,255,255,0.1);
      border-radius: 14px; z-index: 99999; overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      display: none; flex-direction: column;
      animation: vai-slide-up 0.2s ease-out;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .vai-mode-menu.show { display: flex; }
    .vai-mode-btn {
      display: flex; align-items: center; gap: 12px;
      padding: 14px 20px; background: none; border: none;
      color: #e0e0ea; cursor: pointer; font-size: 14px;
      transition: background 0.15s; white-space: nowrap;
      font-family: inherit;
    }
    .vai-mode-btn:hover { background: rgba(255,255,255,0.06); }
    .vai-mode-btn + .vai-mode-btn { border-top: 1px solid rgba(255,255,255,0.06); }
    .vai-mode-btn svg { color: ${ACCENT}; flex-shrink: 0; }
    .vai-mode-label { display: flex; flex-direction: column; gap: 2px; text-align: left; }
    .vai-mode-label span:first-child { font-weight: 600; font-size: 13px; }
    .vai-mode-label span:last-child { font-size: 11px; color: rgba(255,255,255,0.4); }

    @keyframes vai-slide-up {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* ── Voice status ── */
    .vai-status {
      position: fixed; ${POS_SIDE}: 24px; bottom: 92px;
      background: #1a1a2e; color: #fff; padding: 10px 16px;
      border-radius: 12px; font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      z-index: 99998; border: 1px solid rgba(255,255,255,0.1);
      display: none; align-items: center; gap: 8px; max-width: 280px;
    }
    .vai-status.show { display: flex; }
    .vai-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: vai-blink 1s infinite; }
    @keyframes vai-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    .vai-status-fallback {
      margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.1);
    }
    .vai-fallback-btn {
      background: ${ACCENT}; color: #0a0a0f; border: none; border-radius: 6px;
      padding: 6px 12px; font-size: 12px; font-weight: 600; cursor: pointer;
      font-family: inherit; margin-top: 4px;
    }
    .vai-fallback-btn:hover { opacity: 0.9; }

    /* ── Chat panel ── */
    .vai-chat-panel {
      position: fixed; bottom: 92px; ${POS_SIDE}: 24px; z-index: 99999;
      width: 380px; max-width: calc(100vw - 32px);
      height: 520px; max-height: calc(100vh - 120px);
      background: #0f0f17; border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px; display: none; flex-direction: column; overflow: hidden;
      box-shadow: 0 12px 48px rgba(0,0,0,0.5);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      animation: vai-slide-up 0.25s ease-out;
    }
    .vai-chat-panel.open { display: flex; }

    .vai-chat-header {
      display: flex; align-items: center; gap: 10px; padding: 14px 16px;
      background: linear-gradient(135deg, ${ACCENT}15, ${ACCENT}08);
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .vai-chat-avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: ${ACCENT}30; display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0; color: ${ACCENT};
    }
    .vai-chat-header-info { flex: 1; min-width: 0; }
    .vai-chat-header-name { color: #f0f0f5; font-size: 14px; font-weight: 600; }
    .vai-chat-header-sub { color: rgba(255,255,255,0.45); font-size: 11px; }
    .vai-chat-close {
      background: none; border: none; cursor: pointer; padding: 4px;
      color: rgba(255,255,255,0.4); transition: color 0.15s;
    }
    .vai-chat-close:hover { color: #fff; }

    .vai-chat-messages {
      flex: 1; overflow-y: auto; padding: 16px;
      display: flex; flex-direction: column; gap: 10px;
      scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent;
    }
    .vai-chat-messages::-webkit-scrollbar { width: 4px; }
    .vai-chat-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

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
      align-self: flex-end; background: ${ACCENT}; color: #0a0a0f; font-weight: 500;
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

    .vai-chat-input-area {
      display: flex; align-items: center; gap: 8px; padding: 12px 14px;
      border-top: 1px solid rgba(255,255,255,0.06); background: rgba(0,0,0,0.2);
    }
    .vai-chat-input {
      flex: 1; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
      border-radius: 22px; padding: 10px 16px; color: #f0f0f5; font-size: 13.5px;
      outline: none; transition: border-color 0.2s; font-family: inherit;
    }
    .vai-chat-input::placeholder { color: rgba(255,255,255,0.25); }
    .vai-chat-input:focus { border-color: ${ACCENT}50; }
    .vai-send-btn {
      width: 36px; height: 36px; border-radius: 50%; background: ${ACCENT};
      border: none; cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: opacity 0.15s; flex-shrink: 0; color: #0a0a0f;
    }
    .vai-send-btn:disabled { opacity: 0.3; cursor: default; }

    .vai-powered {
      text-align: center; padding: 6px; font-size: 10px; color: rgba(255,255,255,0.2);
    }
    .vai-powered a { color: rgba(255,255,255,0.35); text-decoration: none; }
    .vai-powered a:hover { color: rgba(255,255,255,0.6); }

    @media (max-width: 440px) {
      .vai-chat-panel {
        width: calc(100vw - 16px); bottom: 8px; ${POS_SIDE}: 8px;
        height: calc(100vh - 80px); max-height: none; border-radius: 12px;
      }
      .vai-mode-menu { ${POS_SIDE}: 16px; bottom: 84px; }
    }
  `;

  // ── Build DOM ──
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // FAB button
  const fab = document.createElement('button');
  fab.className = 'vai-fab';
  fab.innerHTML = ICON_MIC;
  fab.title = TITLE;
  fab.setAttribute('aria-label', TITLE);
  document.body.appendChild(fab);

  // Tooltip
  const tooltip = document.createElement('div');
  tooltip.className = 'vai-tooltip';
  tooltip.textContent = TITLE;
  document.body.appendChild(tooltip);

  // Mode selector menu
  const modeMenu = document.createElement('div');
  modeMenu.className = 'vai-mode-menu';
  modeMenu.innerHTML = `
    <button class="vai-mode-btn" data-mode="voice">
      ${ICON_HEADSET}
      <div class="vai-mode-label">
        <span>Llamada de voz</span>
        <span>Habla con el asistente</span>
      </div>
    </button>
    <button class="vai-mode-btn" data-mode="chat">
      ${ICON_KEYBOARD}
      <div class="vai-mode-label">
        <span>Chat de texto</span>
        <span>Escribe tu mensaje</span>
      </div>
    </button>
  `;
  document.body.appendChild(modeMenu);

  // Voice status
  const statusEl = document.createElement('div');
  statusEl.className = 'vai-status';
  document.body.appendChild(statusEl);

  // Chat panel
  const chatPanel = document.createElement('div');
  chatPanel.className = 'vai-chat-panel';
  chatPanel.innerHTML = `
    <div class="vai-chat-header">
      <div class="vai-chat-avatar">${ICON_HEADSET}</div>
      <div class="vai-chat-header-info">
        <div class="vai-chat-header-name">Cargando...</div>
        <div class="vai-chat-header-sub">en linea</div>
      </div>
      <button class="vai-chat-close">${ICON_CLOSE}</button>
    </div>
    <div class="vai-chat-messages"></div>
    <div class="vai-chat-input-area">
      <input class="vai-chat-input" placeholder="Escribe un mensaje..." autocomplete="off" />
      <button class="vai-send-btn" disabled>${ICON_SEND}</button>
    </div>
    <div class="vai-powered">Powered by <a href="https://innotecnia.app" target="_blank" rel="noopener">Voice AI</a></div>
  `;
  document.body.appendChild(chatPanel);

  const chatMessagesEl = chatPanel.querySelector('.vai-chat-messages');
  const chatInputEl = chatPanel.querySelector('.vai-chat-input');
  const chatSendBtn = chatPanel.querySelector('.vai-send-btn');
  const chatCloseBtn = chatPanel.querySelector('.vai-chat-close');
  const chatNameEl = chatPanel.querySelector('.vai-chat-header-name');
  const chatSubEl = chatPanel.querySelector('.vai-chat-header-sub');

  // ── Helpers ──
  let _connectingInterval = null;

  function showVoiceStatus(text, animated) {
    if (_connectingInterval) { clearInterval(_connectingInterval); _connectingInterval = null; }
    if (animated) {
      const msgs = ['Conectando...', 'Preparando asistente...', 'Casi listo...'];
      let i = 0;
      statusEl.innerHTML = '<span class="vai-dot"></span><span>' + msgs[0] + '</span>';
      statusEl.classList.add('show');
      _connectingInterval = setInterval(() => {
        i = (i + 1) % msgs.length;
        statusEl.innerHTML = '<span class="vai-dot"></span><span>' + msgs[i] + '</span>';
      }, 2500);
    } else {
      statusEl.innerHTML = '<span class="vai-dot"></span><span>' + text + '</span>';
      statusEl.classList.add('show');
    }
  }

  function showMicError(hasChatFallback) {
    if (_connectingInterval) { clearInterval(_connectingInterval); _connectingInterval = null; }
    let html = '<div><div style="font-weight:600;margin-bottom:4px">No se pudo acceder al microfono</div>';
    html += '<div style="font-size:11px;color:rgba(255,255,255,0.5)">Verifica los permisos del navegador</div>';
    if (hasChatFallback) {
      html += '<div class="vai-status-fallback"><div style="font-size:11px;color:rgba(255,255,255,0.5)">O puedes escribir tu mensaje:</div>';
      html += '<button class="vai-fallback-btn" id="vai-fallback-chat">Abrir chat de texto</button></div>';
    }
    html += '</div>';
    statusEl.innerHTML = html;
    statusEl.classList.add('show');
    if (hasChatFallback) {
      document.getElementById('vai-fallback-chat')?.addEventListener('click', () => {
        hideVoiceStatus();
        voiceState = 'idle';
        fab.classList.remove('connecting', 'active');
        fab.innerHTML = ICON_MIC;
        openChat();
      });
    }
  }

  function hideVoiceStatus() {
    if (_connectingInterval) { clearInterval(_connectingInterval); _connectingInterval = null; }
    statusEl.classList.remove('show');
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  // ── Config ──
  async function fetchConfig() {
    const res = await fetch(API_BASE + '/widget/config/' + AGENT_SLUG);
    if (!res.ok) throw new Error('Agent not found');
    return res.json();
  }

  async function ensureConfig() {
    if (!config) {
      config = await fetchConfig();
      channels = config.widget_channels || ['voice'];
      // Update FAB icon based on available channels
      if (channels.length === 1 && channels[0] === 'chat') {
        fab.innerHTML = ICON_CHAT;
        fab.title = 'Chat con asistente';
        tooltip.textContent = 'Chat con asistente';
      }
      // Update chat panel header
      chatNameEl.textContent = config.agent_name || 'Asistente';
      chatSubEl.textContent = config.client_name || 'en linea';
    }
    return config;
  }

  // ── Voice logic ──
  async function startVoiceCall() {
    if (voiceState !== 'idle') return;
    mode = 'voice';
    voiceState = 'connecting';
    fab.classList.add('connecting');
    fab.innerHTML = ICON_MIC;
    modeMenu.classList.remove('show');
    showVoiceStatus('Conectando...', true);

    try {
      await ensureConfig();
      const tokenRes = await fetch(API_BASE + '/widget/token/' + AGENT_SLUG, { method: 'POST' });
      if (!tokenRes.ok) throw new Error('Could not get token');
      const tokenData = await tokenRes.json();

      if (!window.LivekitClient) {
        await loadScript('https://cdn.jsdelivr.net/npm/livekit-client@2/dist/livekit-client.umd.js');
      }

      const lk = window.LivekitClient;
      room = new lk.Room({
        audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true },
      });

      room.on(lk.RoomEvent.Disconnected, () => { endVoiceCall(); });

      room.on(lk.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === 'audio') {
          const prev = document.getElementById('vai-audio');
          if (prev) prev.remove();
          const el = track.attach();
          el.id = 'vai-audio';
          el.autoplay = true;
          el.style.display = 'none';
          document.body.appendChild(el);
          el.play().catch((err) => {
            console.warn('[VoiceAI Widget] Audio autoplay blocked:', err.name);
            const unlock = () => { el.play().catch(() => {}); document.removeEventListener('click', unlock); };
            document.addEventListener('click', unlock);
          });
          // Agent audio arrived — NOW show "Hablando con..."
          if (voiceState === 'connecting') {
            voiceState = 'active';
            fab.classList.remove('connecting');
            fab.classList.add('active');
            fab.innerHTML = ICON_STOP;
            showVoiceStatus('Hablando con ' + (config.agent_name || 'asistente') + '...');
          }
        }
      });

      await room.connect(tokenData.url, tokenData.token);

      // Try to enable microphone — this is where permission errors happen
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
      } catch (micErr) {
        console.error('[VoiceAI Widget] Microphone error:', micErr);
        room.disconnect();
        room = null;
        voiceState = 'error';
        fab.classList.remove('connecting');
        const hasChatFallback = channels.includes('chat');
        showMicError(hasChatFallback);
        if (!hasChatFallback) {
          setTimeout(() => { voiceState = 'idle'; hideVoiceStatus(); mode = null; }, 5000);
        }
        return;
      }

      // Mic enabled — keep "connecting" animation until agent audio arrives
      voiceState = 'connecting';

    } catch (err) {
      console.error('[VoiceAI Widget]', err);
      voiceState = 'error';
      fab.classList.remove('connecting');
      showVoiceStatus('Error al conectar');
      setTimeout(() => { voiceState = 'idle'; hideVoiceStatus(); mode = null; }, 3000);
    }
  }

  function endVoiceCall() {
    if (room) {
      try { room.disconnect(); } catch (e) { /* ignore */ }
      room = null;
    }
    const audioEl = document.getElementById('vai-audio');
    if (audioEl) audioEl.remove();
    voiceState = 'idle';
    mode = null;
    fab.classList.remove('active', 'connecting');
    fab.innerHTML = channels.length === 1 && channels[0] === 'chat' ? ICON_CHAT : ICON_MIC;
    hideVoiceStatus();
  }

  // ── Chat logic ──
  function addChatMessage(role, text) {
    chatMessages.push({ role, text });
    const div = document.createElement('div');
    div.className = 'vai-msg vai-msg-' + role;
    div.textContent = text;
    chatMessagesEl.appendChild(div);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  }

  function showTyping() {
    const el = document.createElement('div');
    el.className = 'vai-typing';
    el.id = 'vai-typing';
    el.innerHTML = '<div class="vai-typing-dot"></div><div class="vai-typing-dot"></div><div class="vai-typing-dot"></div>';
    chatMessagesEl.appendChild(el);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('vai-typing');
    if (el) el.remove();
  }

  async function openChat() {
    mode = 'chat';
    chatOpen = true;
    modeMenu.classList.remove('show');
    chatPanel.classList.add('open');
    fab.innerHTML = ICON_CLOSE;
    fab.title = 'Cerrar chat';

    await ensureConfig();
    chatNameEl.textContent = config.agent_name || 'Asistente';
    chatSubEl.textContent = config.client_name || 'en linea';

    if (!conversationId) {
      showTyping();
      try {
        const res = await fetch(API_BASE + '/widget/chat/' + AGENT_SLUG, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: '' }),
        });
        if (!res.ok) throw new Error('Init failed');
        const data = await res.json();
        conversationId = data.conversation_id;
        hideTyping();
        addChatMessage('agent', data.text);
      } catch (e) {
        hideTyping();
        addChatMessage('agent', config?.greeting || 'Hola! En que puedo ayudarte?');
      }
    }
    chatInputEl.focus();
  }

  function closeChat() {
    chatOpen = false;
    mode = null;
    chatPanel.classList.remove('open');
    fab.innerHTML = channels.length === 1 && channels[0] === 'chat' ? ICON_CHAT : ICON_MIC;
    fab.title = TITLE;
  }

  async function sendChatMessage(text) {
    if (!text.trim() || chatLoading) return;
    addChatMessage('user', text.trim());
    chatInputEl.value = '';
    chatSendBtn.disabled = true;
    chatLoading = true;
    showTyping();

    try {
      const res = await fetch(API_BASE + '/widget/chat/' + AGENT_SLUG, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, message: text.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Error');
      }
      const data = await res.json();
      conversationId = data.conversation_id;
      hideTyping();
      addChatMessage('agent', data.text);
    } catch (e) {
      hideTyping();
      addChatMessage('agent', 'Lo siento, hubo un error. Intenta de nuevo.');
      console.error('[VoiceAI Widget]', e);
    } finally {
      chatLoading = false;
      chatSendBtn.disabled = false;
      chatInputEl.focus();
    }
  }

  // ── Mode selector ──
  let menuVisible = false;

  function showModeMenu() {
    menuVisible = true;
    modeMenu.classList.add('show');
  }

  function hideModeMenu() {
    menuVisible = false;
    modeMenu.classList.remove('show');
  }

  // ── FAB click handler ──
  fab.addEventListener('click', async () => {
    // If voice call is active or connecting (mic on, waiting for agent), end it
    if (mode === 'voice' && (voiceState === 'active' || voiceState === 'connecting')) {
      endVoiceCall();
      return;
    }

    // If chat is open, close it
    if (mode === 'chat' && chatOpen) {
      closeChat();
      return;
    }

    // If mic error with fallback visible, ignore
    if (voiceState === 'error') {
      hideVoiceStatus();
      voiceState = 'idle';
      mode = null;
      fab.classList.remove('connecting');
      fab.innerHTML = channels.length === 1 && channels[0] === 'chat' ? ICON_CHAT : ICON_MIC;
      return;
    }

    // Load config first time
    await ensureConfig();

    // Single channel — go direct
    if (channels.length === 1) {
      if (channels[0] === 'voice') {
        startVoiceCall();
      } else {
        openChat();
      }
      return;
    }

    // Both channels — toggle mode menu
    if (menuVisible) {
      hideModeMenu();
    } else {
      showModeMenu();
    }
  });

  // Mode menu buttons
  modeMenu.querySelectorAll('.vai-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const selectedMode = btn.getAttribute('data-mode');
      hideModeMenu();
      if (selectedMode === 'voice') {
        startVoiceCall();
      } else {
        openChat();
      }
    });
  });

  // Chat close button
  chatCloseBtn.addEventListener('click', () => { closeChat(); });

  // Chat send
  chatSendBtn.addEventListener('click', () => { sendChatMessage(chatInputEl.value); });

  chatInputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(chatInputEl.value);
    }
  });

  chatInputEl.addEventListener('input', () => {
    chatSendBtn.disabled = !chatInputEl.value.trim() || chatLoading;
  });

  // Close mode menu when clicking outside
  document.addEventListener('click', (e) => {
    if (menuVisible && !modeMenu.contains(e.target) && !fab.contains(e.target)) {
      hideModeMenu();
    }
  });

  // ── Preload config ──
  ensureConfig().catch(() => {});
})();
