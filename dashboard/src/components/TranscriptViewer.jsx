import { Bot, User } from 'lucide-react'

function isAgent(role) {
  return role === 'agent' || role === 'assistant'
}

export function TranscriptViewer({ transcript = [] }) {
  if (!transcript || !transcript.length) {
    return <p className="text-text-muted text-sm py-4">Sin transcripción disponible</p>
  }

  return (
    <div className="space-y-3">
      {transcript.map((entry, i) => {
        const agent = isAgent(entry.role)
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
              {/* Label */}
              <span className={`text-[10px] font-semibold uppercase tracking-wider block mb-0.5 ${
                agent ? 'text-accent/70' : 'text-purple-400/70'
              }`}>
                {agent ? 'Agente' : 'Cliente'}
              </span>
              {entry.text}
            </div>
          </div>
        )
      })}
    </div>
  )
}
