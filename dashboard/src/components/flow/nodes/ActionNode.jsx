import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const ACTION_LABELS = {
  search_knowledge: 'Buscar info',
  schedule_appointment: 'Agendar cita',
  send_whatsapp: 'WhatsApp',
  save_contact: 'Guardar contacto',
  transfer_to_human: 'Transferir',
}

export const ActionNode = memo(({ data, selected }) => {
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[180px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-[#00f0ff] ring-2 ring-[#00f0ff]/30' : 'border-[#00f0ff]/50'}
      bg-[#1a1a2e]
    `}>
      {hasErrors && (
        <div className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
          {errors.length}
        </div>
      )}
    <Handle
      type="target"
      position={Position.Top}
      className="!bg-[#00f0ff] !border-[#0a0a0f] !w-3 !h-3"
    />
    <div className="flex items-center gap-2 mb-2">
      <div className="w-3 h-3 rounded-full bg-[#00f0ff]" />
      <span className="text-xs font-bold uppercase tracking-wider text-[#00f0ff]">
        {data.label || 'Accion'}
      </span>
    </div>
    <p className="text-sm text-[#e8e8f0] font-medium truncate max-w-[160px]">
      {ACTION_LABELS[data.actionType] || (
        data.actionType?.startsWith('mcp:')
          ? data.actionType.split(':').slice(2).join(':')
          : data.actionType?.startsWith('api:')
            ? data.actionType.slice(4)
            : data.actionType || 'Seleccionar...'
      )}
    </p>
    {data.actionType?.startsWith('mcp:') && (
      <p className="text-[10px] text-[#00f0ff]/60 mt-0.5">
        MCP: {data.actionType.split(':')[1]}
      </p>
    )}
    {data.actionType?.startsWith('api:') && (
      <p className="text-[10px] text-[#00f0ff]/60 mt-0.5">
        API: {data.actionType.slice(4)}
      </p>
    )}
    {data.resultVariable && (
      <p className="text-xs text-[#8888a0] font-mono mt-1">{`-> {${data.resultVariable}}`}</p>
    )}
    {hasErrors && (
      <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
    )}
    {/* Dual handles: success (left) / failure (right) */}
    <Handle
      type="source"
      position={Position.Bottom}
      id="success"
      className="!bg-green-400 !border-[#0a0a0f] !w-3 !h-3"
      style={{ left: '30%' }}
    />
    <Handle
      type="source"
      position={Position.Bottom}
      id="failure"
      className="!bg-red-400 !border-[#0a0a0f] !w-3 !h-3"
      style={{ left: '70%' }}
    />
    <div className="flex justify-between mt-2 text-[10px] text-[#8888a0]">
      <span>OK</span>
      <span>Error</span>
    </div>
  </div>
  )
})

ActionNode.displayName = 'ActionNode'
