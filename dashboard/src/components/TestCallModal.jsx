import { useState, useEffect, useRef, useCallback } from 'react'
import { PhoneOff, Mic, MicOff, Loader2 } from 'lucide-react'
import { Room, RoomEvent, ConnectionState, Track } from 'livekit-client'
import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { api } from '../lib/api'

/**
 * Modal para realizar llamadas de prueba a un agente desde el navegador.
 * Usa la API de widget token para conectar via LiveKit con audio solamente.
 */
export function TestCallModal({ agentSlug, agentName, open, onClose }) {
  const [status, setStatus] = useState('idle') // idle | connecting | connected | error | disconnected
  const [error, setError] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [muted, setMuted] = useState(false)

  const roomRef = useRef(null)
  const timerRef = useRef(null)
  const startTimeRef = useRef(null)
  const cleaningUpRef = useRef(false)

  const cleanup = useCallback(async () => {
    if (cleaningUpRef.current) return
    cleaningUpRef.current = true

    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    if (roomRef.current) {
      try {
        await roomRef.current.disconnect(true)
      } catch {
        // ignorar errores al desconectar
      }
      roomRef.current = null
    }

    cleaningUpRef.current = false
  }, [])

  // Conectar al abrir el modal
  useEffect(() => {
    if (!open || !agentSlug) return

    let cancelled = false

    async function connect() {
      setStatus('connecting')
      setError(null)
      setElapsed(0)

      try {
        // Obtener token del endpoint de widget
        const { token, url } = await api.post(`/widget/token/${agentSlug}`)

        if (cancelled) return

        const room = new Room({
          audioCaptureDefaults: { autoGainControl: true, noiseSuppression: true, echoCancellation: true },
          adaptiveStream: false,
          dynacast: false,
        })
        roomRef.current = room

        // Escuchar eventos
        room.on(RoomEvent.ConnectionStateChanged, (state) => {
          if (cancelled) return
          if (state === ConnectionState.Connected) {
            setStatus('connected')
            startTimeRef.current = Date.now()
            timerRef.current = setInterval(() => {
              setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000))
            }, 1000)
          } else if (state === ConnectionState.Disconnected) {
            setStatus('disconnected')
            if (timerRef.current) {
              clearInterval(timerRef.current)
              timerRef.current = null
            }
          }
        })

        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach()
            el.id = 'test-call-audio'
            document.body.appendChild(el)
          }
        })

        room.on(RoomEvent.TrackUnsubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const elements = track.detach()
            elements.forEach(el => el.remove())
          }
        })

        room.on(RoomEvent.Disconnected, () => {
          if (cancelled) return
          setStatus('disconnected')
          if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
          }
        })

        // Conectar con audio solamente
        await room.connect(url, token, {
          autoSubscribe: true,
        })

        if (cancelled) {
          await room.disconnect(true)
          return
        }

        // Publicar microfono
        await room.localParticipant.setMicrophoneEnabled(true)
      } catch (err) {
        if (cancelled) return
        setStatus('error')
        setError(err.message || 'Error al conectar')
      }
    }

    connect()

    return () => {
      cancelled = true
      cleanup()
    }
  }, [open, agentSlug, cleanup])

  // Cleanup al desmontar
  useEffect(() => {
    return () => { cleanup() }
  }, [cleanup])

  function handleHangup() {
    cleanup()
    onClose()
  }

  function handleClose() {
    cleanup()
    onClose()
  }

  function toggleMute() {
    if (!roomRef.current) return
    const newMuted = !muted
    roomRef.current.localParticipant.setMicrophoneEnabled(!newMuted)
    setMuted(newMuted)
  }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  return (
    <Modal open={open} onClose={handleClose} title="Llamada de prueba" maxWidth="max-w-sm">
      <div className="flex flex-col items-center py-6 space-y-6">
        {/* Indicador de estado visual */}
        <div className="relative">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center ${
            status === 'connecting' ? 'bg-accent/10 border-2 border-accent/30' :
            status === 'connected' ? 'bg-green-500/10 border-2 border-green-500/40' :
            status === 'error' ? 'bg-red-500/10 border-2 border-red-500/40' :
            status === 'disconnected' ? 'bg-text-muted/10 border-2 border-border' :
            'bg-accent/10 border-2 border-accent/30'
          }`}>
            {status === 'connecting' && (
              <Loader2 size={32} className="text-accent animate-spin" />
            )}
            {status === 'connected' && (
              <div className="w-4 h-4 rounded-full bg-green-500 animate-pulse" />
            )}
            {status === 'error' && (
              <PhoneOff size={28} className="text-red-400" />
            )}
            {status === 'disconnected' && (
              <PhoneOff size={28} className="text-text-muted" />
            )}
          </div>
          {status === 'connected' && (
            <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-green-500 border-2 border-[#0a0a0f]" />
          )}
        </div>

        {/* Info del agente */}
        <div className="text-center space-y-1">
          <p className="text-lg font-semibold">{agentName}</p>
          <p className={`text-sm ${
            status === 'connecting' ? 'text-accent' :
            status === 'connected' ? 'text-green-400' :
            status === 'error' ? 'text-red-400' :
            status === 'disconnected' ? 'text-text-muted' :
            'text-text-muted'
          }`}>
            {status === 'connecting' && 'Conectando...'}
            {status === 'connected' && 'En llamada'}
            {status === 'error' && 'Error de conexion'}
            {status === 'disconnected' && 'Llamada finalizada'}
          </p>
        </div>

        {/* Timer */}
        {(status === 'connected' || status === 'disconnected') && (
          <p className="font-mono text-2xl text-text-secondary tabular-nums">
            {formatTime(elapsed)}
          </p>
        )}

        {/* Error */}
        {status === 'error' && error && (
          <p className="text-xs text-red-400 text-center max-w-[250px]">{error}</p>
        )}

        {/* Controles */}
        <div className="flex items-center gap-4">
          {status === 'connected' && (
            <button
              onClick={toggleMute}
              className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors cursor-pointer ${
                muted
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                  : 'bg-bg-card text-text-secondary border border-border hover:bg-bg-hover'
              }`}
              title={muted ? 'Activar microfono' : 'Silenciar microfono'}
            >
              {muted ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
          )}

          {(status === 'connecting' || status === 'connected') && (
            <button
              onClick={handleHangup}
              className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors cursor-pointer"
              title="Colgar"
            >
              <PhoneOff size={24} />
            </button>
          )}

          {(status === 'error' || status === 'disconnected') && (
            <Button variant="secondary" onClick={handleClose}>
              Cerrar
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
