import { Bot, User, Clock } from 'lucide-react'

function isAgent(role) {
  return role === 'agent' || role === 'assistant'
}

function formatElapsed(ms) {
  if (ms == null || isNaN(ms)) return null
  const s = Math.floor(ms / 1000)
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${mm}:${String(ss).padStart(2, '0')}`
}

function formatDelta(ms) {
  if (ms == null || isNaN(ms)) return null
  const s = ms / 1000
  if (s < 1) return `+${Math.round(ms)}ms`
  return `+${s.toFixed(1)}s`
}

export function TranscriptViewer({ transcript = [] }) {
  if (!transcript || !transcript.length) {
    return <p className="text-text-muted text-sm py-4">Sin transcripción disponible</p>
  }

  // Timestamp de la primera entrada para calcular elapsed
  const firstTs = transcript[0]?.timestamp ? new Date(transcript[0].timestamp).getTime() : null

  return (
    <div className="space-y-3">
      {transcript.map((entry, i) => {
        const agent = isAgent(entry.role)
        const ts = entry.timestamp ? new Date(entry.timestamp).getTime() : null
        const elapsed = (ts && firstTs) ? ts - firstTs : null
        const prevTs = i > 0 && transcript[i - 1]?.timestamp
          ? new Date(transcript[i - 1].timestamp).getTime()
          : null
        const delta = (ts && prevTs) ? ts - prevTs : null
        // Destacar gaps largos (más de 5s) que indican latencia o silencio
        const isLongGap = delta != null && delta > 5000

        return (
          <div key={i} className={`flex gap-3 ${agent ? '' : 'flex-row-reverse'}`}>
            {/* Avatar */}
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
              agent ? 'bg-accent/20' : 'bg-purple-500/20'
            }`}>
              {agent
                ? <Bot size={14} className="text-accent" />
                : <User size={14} className="text-purple-400" />
              }
            </div>

            {/* Bubble */}
            <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              agent
                ? 'bg-bg-card border border-accent/30'
                : 'bg-purple-500/10 border border-purple-500/20'
            }`}>
              {/* Header: label + timestamps */}
              <div className={`flex items-center gap-2 mb-0.5 ${agent ? '' : 'flex-row-reverse'}`}>
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${
                  agent ? 'text-accent/70' : 'text-purple-400/70'
                }`}>
                  {agent ? 'Agente' : 'Cliente'}
                </span>
                {elapsed != null && (
                  <span className="text-[10px] text-text-muted font-mono flex items-center gap-0.5">
                    <Clock size={9} /> {formatElapsed(elapsed)}
                  </span>
                )}
                {delta != null && i > 0 && (
                  <span className={`text-[10px] font-mono ${
                    isLongGap ? 'text-yellow-400 font-semibold' : 'text-text-muted/60'
                  }`} title={isLongGap ? 'Pausa larga' : undefined}>
                    {formatDelta(delta)}
                  </span>
                )}
              </div>
              {entry.text}
            </div>
          </div>
        )
      })}
    </div>
  )
}
