import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Upload, Mic, Play, Square, Trash2, Check, AlertCircle, Volume2, Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { supabase } from '../lib/supabase'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

/**
 * Componente de clonación de voces.
 * Permite grabar/subir audio, clonar la voz, previsualizar y asignar a un agente.
 */
export function VoiceCloning({ clientId, agentId, currentVoiceId, onVoiceAssigned, onClonedVoicesChange }) {
  const [clonedVoices, setClonedVoices] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  // Grabación
  const [recording, setRecording] = useState(false)
  const [recordedBlob, setRecordedBlob] = useState(null)
  const [recordingTime, setRecordingTime] = useState(0)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)

  // Upload file
  const fileInputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)

  // Form
  const [voiceName, setVoiceName] = useState('')

  // Preview
  const [playingId, setPlayingId] = useState(null)
  const audioRef = useRef(null)

  const loadClonedVoices = useCallback(async () => {
    if (!clientId) return
    try {
      setLoading(true)
      const data = await api.get(`/voices/cloned/${clientId}`)
      setClonedVoices(data)
      onClonedVoicesChange?.(data)
    } catch (e) {
      console.error('Error cargando voces clonadas:', e)
    } finally {
      setLoading(false)
    }
  }, [clientId])

  useEffect(() => {
    loadClonedVoices()
  }, [loadClonedVoices])

  // ── Grabación de audio ──

  async function startRecording() {
    try {
      setError(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setRecordedBlob(blob)
        stream.getTracks().forEach(t => t.stop())
      }

      mediaRecorder.start()
      setRecording(true)
      setRecordingTime(0)
      timerRef.current = setInterval(() => {
        setRecordingTime(t => t + 1)
      }, 1000)
    } catch (e) {
      setError('No se pudo acceder al microfono. Verifica los permisos del navegador.')
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
      clearInterval(timerRef.current)
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)

    const maxSize = 10 * 1024 * 1024
    if (file.size > maxSize) {
      setError('El archivo es demasiado grande (max 10MB)')
      return
    }

    setSelectedFile(file)
    setRecordedBlob(null)
  }

  function clearAudioSelection() {
    setRecordedBlob(null)
    setSelectedFile(null)
    setRecordingTime(0)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // ── Clonar voz ──

  async function handleClone() {
    const audioSource = recordedBlob || selectedFile
    if (!audioSource || !voiceName.trim()) {
      setError('Necesitas un nombre y un audio para clonar la voz')
      return
    }

    setUploading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('audio', audioSource, audioSource.name || 'recording.webm')
      formData.append('name', voiceName.trim())
      formData.append('client_id', clientId)
      formData.append('provider', 'cartesia')
      formData.append('language', 'es')
      if (agentId) formData.append('agent_id', agentId)

      await api.upload('/voices/clone', formData)

      setVoiceName('')
      clearAudioSelection()
      await loadClonedVoices()
    } catch (e) {
      setError(e.message || 'Error clonando la voz')
    } finally {
      setUploading(false)
    }
  }

  // ── Preview ──

  async function handlePreview(voice) {
    if (playingId === voice.id) {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      setPlayingId(null)
      return
    }

    setPlayingId(voice.id)
    try {
      const { data } = await supabase.auth.getSession()
      const token = data?.session?.access_token
      const resp = await fetch(
        `${API_BASE}/voices/cloned/${voice.id}/preview?text=${encodeURIComponent('Hola, esta es mi voz clonada. ¿Como suena?')}`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
      )

      if (!resp.ok) throw new Error('Error generando preview')

      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio

      audio.onended = () => {
        setPlayingId(null)
        URL.revokeObjectURL(url)
      }
      audio.onerror = () => {
        setPlayingId(null)
        URL.revokeObjectURL(url)
      }

      await audio.play()
    } catch (e) {
      console.error('Error en preview:', e)
      setPlayingId(null)
      setError('Error reproduciendo preview')
    }
  }

  // ── Asignar ──

  async function handleAssign(voice) {
    try {
      await api.post(`/voices/cloned/${voice.id}/assign?agent_id=${agentId}`)
      onVoiceAssigned?.(voice.external_voice_id)
      await loadClonedVoices()
    } catch (e) {
      setError(e.message || 'Error asignando la voz')
    }
  }

  // ── Eliminar ──

  async function handleDelete(voice) {
    try {
      await api.delete(`/voices/cloned/${voice.id}`)
      await loadClonedVoices()
      if (audioRef.current && playingId === voice.id) {
        audioRef.current.pause()
        setPlayingId(null)
      }
    } catch (e) {
      setError(e.message || 'Error eliminando la voz')
    }
  }

  const hasAudio = !!recordedBlob || !!selectedFile
  const audioLabel = recordedBlob
    ? `Grabacion (${recordingTime}s)`
    : selectedFile
      ? selectedFile.name
      : null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Mic size={16} className="text-accent" />
        <span className="text-sm font-medium">Clonacion de Voz</span>
      </div>
      <p className="text-xs text-text-muted">
        Clona una voz a partir de una grabacion o archivo de audio (5-30 segundos, sin ruido de fondo).
        La voz clonada se puede asignar a este agente.
      </p>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
          <AlertCircle size={14} />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400/60 hover:text-red-400 cursor-pointer">&times;</button>
        </div>
      )}

      {/* Captura de audio */}
      <div className="p-4 rounded-lg border border-border bg-bg-primary/50 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <Volume2 size={14} className="text-text-muted" />
          <span className="text-xs font-medium text-text-secondary">Fuente de audio</span>
        </div>

        <div className="flex gap-2">
          {/* Grabar */}
          <button
            type="button"
            onClick={recording ? stopRecording : startRecording}
            disabled={uploading}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
              recording
                ? 'border-red-500 bg-red-500/10 text-red-400 animate-pulse'
                : 'border-border bg-bg-secondary text-text-secondary hover:bg-bg-hover'
            }`}
          >
            {recording ? (
              <>
                <Square size={14} />
                <span>Parar ({recordingTime}s)</span>
              </>
            ) : (
              <>
                <Mic size={14} />
                <span>Grabar</span>
              </>
            )}
          </button>

          {/* Subir archivo */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={recording || uploading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-bg-secondary text-text-secondary text-xs font-medium hover:bg-bg-hover cursor-pointer"
          >
            <Upload size={14} />
            <span>Subir archivo</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>

        {/* Audio seleccionado */}
        {hasAudio && (
          <div className="flex items-center gap-2 px-3 py-2 bg-accent/5 border border-accent/20 rounded-lg">
            <Check size={14} className="text-accent" />
            <span className="text-xs text-accent">{audioLabel}</span>
            <button
              type="button"
              onClick={clearAudioSelection}
              className="ml-auto text-text-muted hover:text-red-400 cursor-pointer"
            >
              <Trash2 size={12} />
            </button>
          </div>
        )}

        {/* Nombre + boton clonar */}
        <div className="flex gap-2">
          <input
            type="text"
            value={voiceName}
            onChange={e => setVoiceName(e.target.value)}
            placeholder="Nombre de la voz (ej: 'Mi voz', 'Dr. Garcia')"
            maxLength={100}
            className="flex-1 bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/50 transition-colors"
          />
          <button
            type="button"
            onClick={handleClone}
            disabled={!hasAudio || !voiceName.trim() || uploading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-bg-primary text-sm font-medium hover:bg-accent/90 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            {uploading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Mic size={14} />
            )}
            <span>{uploading ? 'Clonando...' : 'Clonar'}</span>
          </button>
        </div>
      </div>

      {/* Lista de voces clonadas */}
      {loading ? (
        <div className="flex items-center gap-2 py-3 text-xs text-text-muted">
          <Loader2 size={14} className="animate-spin" />
          Cargando voces clonadas...
        </div>
      ) : clonedVoices.length > 0 ? (
        <div className="space-y-2">
          <span className="text-xs font-medium text-text-secondary">Voces clonadas ({clonedVoices.length})</span>
          {clonedVoices.map(voice => {
            const isAssigned = currentVoiceId === voice.external_voice_id
            const isPlaying = playingId === voice.id

            return (
              <div
                key={voice.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all ${
                  isAssigned
                    ? 'border-accent/40 bg-accent/5'
                    : 'border-border bg-bg-primary/50 hover:bg-bg-hover'
                }`}
              >
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{voice.name}</span>
                    {isAssigned && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent font-medium">
                        EN USO
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-text-muted truncate">
                    {voice.provider === 'cartesia' ? 'Cartesia' : 'ElevenLabs'} &middot; {voice.language}
                    {voice.description ? ` — ${voice.description}` : ''}
                  </p>
                </div>

                {/* Acciones */}
                <div className="flex items-center gap-1">
                  {/* Preview */}
                  <button
                    type="button"
                    onClick={() => handlePreview(voice)}
                    className="p-1.5 rounded-md text-text-muted hover:text-accent hover:bg-accent/10 transition-all cursor-pointer"
                    title={isPlaying ? 'Detener' : 'Escuchar preview'}
                  >
                    {isPlaying ? (
                      <Square size={14} className="text-accent" />
                    ) : (
                      <Play size={14} />
                    )}
                  </button>

                  {/* Asignar */}
                  {!isAssigned && agentId && (
                    <button
                      type="button"
                      onClick={() => handleAssign(voice)}
                      className="p-1.5 rounded-md text-text-muted hover:text-green-400 hover:bg-green-400/10 transition-all cursor-pointer"
                      title="Usar esta voz"
                    >
                      <Check size={14} />
                    </button>
                  )}

                  {/* Eliminar */}
                  <button
                    type="button"
                    onClick={() => handleDelete(voice)}
                    className="p-1.5 rounded-md text-text-muted hover:text-red-400 hover:bg-red-400/10 transition-all cursor-pointer"
                    title="Eliminar"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-xs text-text-muted py-2">
          No tienes voces clonadas. Graba o sube un audio para crear una.
        </p>
      )}
    </div>
  )
}
