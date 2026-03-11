import { useEffect, useRef, useState, useCallback } from 'react'
import { Play, Pause, Download, Trash2, Volume2, VolumeX, Loader2 } from 'lucide-react'

const SPEEDS = [0.5, 1, 1.5, 2]

function formatTime(seconds) {
  if (!seconds || !isFinite(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function AudioPlayer({ url, onDelete }) {
  const audioRef = useRef(null)
  const progressRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [volume, setVolume] = useState(1)
  const [muted, setMuted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onLoaded = () => {
      setDuration(audio.duration)
      setLoading(false)
    }
    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onEnded = () => setPlaying(false)
    const onError = () => {
      setError('Error al cargar la grabacion')
      setLoading(false)
    }
    const onWaiting = () => setLoading(true)
    const onCanPlay = () => setLoading(false)

    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('error', onError)
    audio.addEventListener('waiting', onWaiting)
    audio.addEventListener('canplay', onCanPlay)

    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('error', onError)
      audio.removeEventListener('waiting', onWaiting)
      audio.removeEventListener('canplay', onCanPlay)
    }
  }, [url])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
    } else {
      audio.play().catch(() => setError('No se pudo reproducir'))
    }
    setPlaying(!playing)
  }, [playing])

  const handleSeek = useCallback((e) => {
    const audio = audioRef.current
    const bar = progressRef.current
    if (!audio || !bar) return
    const rect = bar.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    audio.currentTime = pct * duration
    setCurrentTime(audio.currentTime)
  }, [duration])

  const cycleSpeed = useCallback(() => {
    const idx = SPEEDS.indexOf(speed)
    const next = SPEEDS[(idx + 1) % SPEEDS.length]
    setSpeed(next)
    if (audioRef.current) audioRef.current.playbackRate = next
  }, [speed])

  const toggleMute = useCallback(() => {
    if (audioRef.current) audioRef.current.muted = !muted
    setMuted(!muted)
  }, [muted])

  const handleVolumeChange = useCallback((e) => {
    const v = parseFloat(e.target.value)
    setVolume(v)
    if (audioRef.current) {
      audioRef.current.volume = v
      audioRef.current.muted = v === 0
      setMuted(v === 0)
    }
  }, [])

  const handleDownload = useCallback(() => {
    if (!url) return
    const a = document.createElement('a')
    a.href = url
    a.download = 'grabacion.wav'
    a.target = '_blank'
    a.click()
  }, [url])

  const handleDelete = useCallback(() => {
    setShowDeleteConfirm(false)
    onDelete?.()
  }, [onDelete])

  if (error) {
    return (
      <div className="bg-bg-secondary border border-border rounded-xl p-4 text-center">
        <p className="text-sm text-text-muted">{error}</p>
      </div>
    )
  }

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className="bg-bg-secondary border border-border rounded-xl p-4 space-y-3">
      <audio ref={audioRef} src={url} preload="metadata" />

      {/* Play + Progress + Time */}
      <div className="flex items-center gap-3">
        {/* Play/Pause */}
        <button
          onClick={togglePlay}
          disabled={loading}
          className="w-10 h-10 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center text-accent hover:bg-accent/30 transition-colors disabled:opacity-50 shrink-0 cursor-pointer"
          title={playing ? 'Pausar' : 'Reproducir'}
        >
          {loading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : playing ? (
            <Pause size={18} />
          ) : (
            <Play size={18} className="ml-0.5" />
          )}
        </button>

        {/* Progress bar */}
        <div className="flex-1 min-w-0">
          <div
            ref={progressRef}
            onClick={handleSeek}
            className="group relative h-2 bg-bg-hover rounded-full cursor-pointer"
          >
            {/* Filled */}
            <div
              className="absolute inset-y-0 left-0 bg-accent rounded-full transition-[width] duration-100"
              style={{ width: `${progress}%` }}
            />
            {/* Thumb */}
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-accent rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
              style={{ left: `calc(${progress}% - 6px)` }}
            />
          </div>
        </div>

        {/* Time */}
        <span className="text-xs font-mono text-text-muted whitespace-nowrap shrink-0">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      {/* Controls row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Speed */}
          <button
            onClick={cycleSpeed}
            className="px-2 py-1 rounded text-[11px] font-mono font-medium bg-bg-hover border border-border text-text-secondary hover:text-text-primary hover:border-accent/30 transition-colors cursor-pointer"
            title="Velocidad de reproduccion"
          >
            {speed}x
          </button>

          {/* Volume */}
          <button
            onClick={toggleMute}
            className="p-1 rounded text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            title={muted ? 'Activar sonido' : 'Silenciar'}
          >
            {muted || volume === 0 ? <VolumeX size={14} /> : <Volume2 size={14} />}
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={muted ? 0 : volume}
            onChange={handleVolumeChange}
            className="w-16 h-1 accent-accent cursor-pointer"
            title="Volumen"
          />
        </div>

        <div className="flex items-center gap-1.5">
          {/* Download */}
          <button
            onClick={handleDownload}
            className="p-1.5 rounded text-text-muted hover:text-accent hover:bg-accent/10 transition-colors cursor-pointer"
            title="Descargar grabacion"
          >
            <Download size={14} />
          </button>

          {/* Delete */}
          {onDelete && (
            <>
              {showDeleteConfirm ? (
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-danger">Eliminar?</span>
                  <button
                    onClick={handleDelete}
                    className="px-2 py-0.5 rounded bg-danger/20 text-danger border border-danger/30 hover:bg-danger/30 transition-colors cursor-pointer"
                  >
                    Si
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="px-2 py-0.5 rounded bg-bg-hover text-text-muted border border-border hover:text-text-primary transition-colors cursor-pointer"
                  >
                    No
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="p-1.5 rounded text-text-muted hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                  title="Eliminar grabacion (GDPR)"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
