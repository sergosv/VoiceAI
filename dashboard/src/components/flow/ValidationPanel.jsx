import React from 'react'

const NODE_TYPE_LABELS = {
  start: 'Inicio',
  message: 'Mensaje',
  collectInput: 'Recopilar Dato',
  condition: 'Condicion',
  action: 'Accion',
  end: 'Fin',
  transfer: 'Transferir',
  wait: 'Espera',
}

export function ValidationPanel({ errors, nodes, onClose, onNavigateToNode }) {
  const allEntries = Object.entries(errors).flatMap(([nodeId, errs]) => {
    const node = nodes.find(n => n.id === nodeId)
    const label = node?.data?.label || NODE_TYPE_LABELS[node?.type] || nodeId
    const type = node?.type || 'unknown'
    return errs.map((msg, i) => ({ nodeId, label, type, msg, key: `${nodeId}-${i}` }))
  })

  const isWarning = (msg) => msg.startsWith('(aviso)')

  const errorCount = allEntries.filter(e => !isWarning(e.msg)).length
  const warningCount = allEntries.filter(e => isWarning(e.msg)).length

  return (
    <div className="absolute right-[320px] top-0 bottom-0 w-[300px] bg-[#12121a] border-l border-[#2a2a3e]
                    flex flex-col z-10 shadow-2xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <span className="text-sm font-medium text-[#e8e8f0]">Validacion</span>
        </div>
        <div className="flex items-center gap-2">
          {errorCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-medium">
              {errorCount} error{errorCount > 1 ? 'es' : ''}
            </span>
          )}
          {warningCount > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 font-medium">
              {warningCount} aviso{warningCount > 1 ? 's' : ''}
            </span>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded text-[#555570] hover:text-[#e8e8f0] hover:bg-[#252540] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {allEntries.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-[#555570]">
            <svg className="w-8 h-8 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm">Sin problemas</span>
          </div>
        )}
        {allEntries.map((entry) => (
          <button
            key={entry.key}
            onClick={() => onNavigateToNode(entry.nodeId)}
            className="w-full text-left px-3 py-2 rounded-lg hover:bg-[#252540] transition-colors group"
          >
            <div className="flex items-center gap-2 mb-0.5">
              <div className={`w-1.5 h-1.5 rounded-full ${isWarning(entry.msg) ? 'bg-yellow-400' : 'bg-red-400'}`} />
              <span className="text-xs font-medium text-[#e8e8f0] truncate">
                {entry.label}
              </span>
              <span className="text-[10px] text-[#555570]">
                {NODE_TYPE_LABELS[entry.type] || entry.type}
              </span>
            </div>
            <p className={`text-[11px] ml-3.5 ${isWarning(entry.msg) ? 'text-yellow-400/80' : 'text-red-400/80'}`}>
              {isWarning(entry.msg) ? entry.msg.replace('(aviso) ', '') : entry.msg}
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}
