/**
 * Voice AI Widget — Embeddable voice agent for websites.
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

  // Prevent double-init
  if (window.__voiceAIWidget) return;
  window.__voiceAIWidget = true;

  // Read config from script tag
  const script = document.currentScript;
  const AGENT_SLUG = script?.getAttribute('data-agent');
  const API_BASE = script?.getAttribute('data-api') || '/api';
  const POSITION = script?.getAttribute('data-position') || 'bottom-right';
  const ACCENT = script?.getAttribute('data-color') || '#00f0ff';
  const TITLE = script?.getAttribute('data-title') || 'Hablar con asistente';

  if (!AGENT_SLUG) {
    console.error('[VoiceAI Widget] Missing data-agent attribute');
    return;
  }

  // State
  let state = 'idle'; // idle | connecting | active | error
  let room = null;
  let config = null;

  // --- Styles ---
  const css = `
    .vai-fab {
      position: fixed;
      ${POSITION === 'bottom-left' ? 'left: 24px' : 'right: 24px'};
      bottom: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: ${ACCENT};
      color: #000;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 20px ${ACCENT}40;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 99999;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .vai-fab:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 28px ${ACCENT}60;
    }
    .vai-fab.active {
      background: #ef4444;
      box-shadow: 0 4px 20px #ef444440;
      animation: vai-pulse 1.5s infinite;
    }
    .vai-fab.connecting {
      opacity: 0.7;
      cursor: wait;
    }
    @keyframes vai-pulse {
      0%, 100% { box-shadow: 0 0 0 0 #ef444440; }
      50% { box-shadow: 0 0 0 12px #ef444400; }
    }
    .vai-tooltip {
      position: fixed;
      ${POSITION === 'bottom-left' ? 'left: 92px' : 'right: 92px'};
      bottom: 38px;
      background: #1a1a2e;
      color: #fff;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      white-space: nowrap;
      z-index: 99998;
      opacity: 0;
      transition: opacity 0.2s;
      pointer-events: none;
      border: 1px solid #ffffff15;
    }
    .vai-fab:hover + .vai-tooltip { opacity: 1; }
    .vai-status {
      position: fixed;
      ${POSITION === 'bottom-left' ? 'left: 24px' : 'right: 24px'};
      bottom: 92px;
      background: #1a1a2e;
      color: #fff;
      padding: 10px 16px;
      border-radius: 12px;
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      z-index: 99998;
      border: 1px solid #ffffff15;
      display: none;
      align-items: center;
      gap: 8px;
      max-width: 260px;
    }
    .vai-status.show { display: flex; }
    .vai-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #22c55e; animation: vai-blink 1s infinite;
    }
    @keyframes vai-blink {
      0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
    }
  `;

  // Mic icon SVG
  const MIC_SVG = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>';
  const STOP_SVG = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';

  // --- DOM ---
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  const fab = document.createElement('button');
  fab.className = 'vai-fab';
  fab.innerHTML = MIC_SVG;
  fab.title = TITLE;
  fab.setAttribute('aria-label', TITLE);
  document.body.appendChild(fab);

  const tooltip = document.createElement('div');
  tooltip.className = 'vai-tooltip';
  tooltip.textContent = TITLE;
  document.body.appendChild(tooltip);

  const statusEl = document.createElement('div');
  statusEl.className = 'vai-status';
  document.body.appendChild(statusEl);

  function showStatus(text) {
    statusEl.innerHTML = `<span class="vai-dot"></span><span>${text}</span>`;
    statusEl.classList.add('show');
  }
  function hideStatus() {
    statusEl.classList.remove('show');
  }

  // --- Logic ---
  async function fetchConfig() {
    const res = await fetch(`${API_BASE}/widget/config/${AGENT_SLUG}`);
    if (!res.ok) throw new Error('Agent not found');
    return res.json();
  }

  async function fetchToken() {
    const res = await fetch(`${API_BASE}/widget/token/${AGENT_SLUG}`, { method: 'POST' });
    if (!res.ok) throw new Error('Could not get token');
    return res.json();
  }

  async function startCall() {
    if (state !== 'idle') return;
    state = 'connecting';
    fab.classList.add('connecting');
    fab.innerHTML = MIC_SVG;
    showStatus('Conectando...');

    try {
      // 1. Get config + token
      if (!config) config = await fetchConfig();
      const tokenData = await fetchToken();

      // 2. Load LiveKit SDK dynamically if not present
      if (!window.LivekitClient) {
        await loadScript('https://cdn.jsdelivr.net/npm/livekit-client@2/dist/livekit-client.umd.js');
      }

      // 3. Connect to room
      const lk = window.LivekitClient;
      room = new lk.Room({
        audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true },
      });

      room.on(lk.RoomEvent.Disconnected, () => {
        endCall();
      });

      room.on(lk.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === 'audio') {
          const el = track.attach();
          el.id = 'vai-audio';
          document.body.appendChild(el);
        }
      });

      await room.connect(tokenData.url, tokenData.token);
      await room.localParticipant.setMicrophoneEnabled(true);

      state = 'active';
      fab.classList.remove('connecting');
      fab.classList.add('active');
      fab.innerHTML = STOP_SVG;
      showStatus(`Hablando con ${config.agent_name}...`);

    } catch (err) {
      console.error('[VoiceAI Widget]', err);
      state = 'error';
      fab.classList.remove('connecting');
      showStatus('Error al conectar');
      setTimeout(() => { state = 'idle'; hideStatus(); }, 3000);
    }
  }

  function endCall() {
    if (room) {
      try { room.disconnect(); } catch (e) { /* ignore */ }
      room = null;
    }
    // Remove audio elements
    const audioEl = document.getElementById('vai-audio');
    if (audioEl) audioEl.remove();

    state = 'idle';
    fab.classList.remove('active', 'connecting');
    fab.innerHTML = MIC_SVG;
    hideStatus();
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

  // --- Events ---
  fab.addEventListener('click', () => {
    if (state === 'idle') startCall();
    else if (state === 'active') endCall();
  });
})();
