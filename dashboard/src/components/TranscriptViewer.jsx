import { Bot, User } from 'lucide-react'

export function TranscriptViewer({ transcript = [] }) {
  if (!transcript || !transcript.length) {
    return <p className="text-text-muted text-sm py-4">Sin transcripción disponible</p>
  }

  return (
    <div className="space-y-3">
      {transcript.map((entry, i) => (
        <div key={i} className={`flex gap-3 ${entry.role === 'agent' ? '' : 'flex-row-reverse'}`}>
          <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
            entry.role === 'agent' ? 'bg-accent/20' : 'bg-bg-hover'
          }`}>
            {entry.role === 'agent' ? <Bot size={14} className="text-accent" /> : <User size={14} />}
          </div>
          <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
            entry.role === 'agent'
              ? 'bg-bg-card border border-border'
              : 'bg-accent/10 border border-accent/20'
          }`}>
            {entry.text}
          </div>
        </div>
      ))}
    </div>
  )
}
