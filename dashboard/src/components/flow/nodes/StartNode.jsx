import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

export const StartNode = memo(({ data, selected }) => {
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[180px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-green-400 ring-2 ring-green-400/30' : 'border-green-500/50'}
      bg-[#1a1a2e]
    `}>
      {hasErrors && (
        <div className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
          {errors.length}
        </div>
      )}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-3 h-3 rounded-full bg-green-500" />
        <span className="text-xs font-bold uppercase tracking-wider text-green-400">Inicio</span>
      </div>
      <p className="text-sm text-[#e8e8f0] line-clamp-2">
        {data.greeting || 'Saludo inicial...'}
      </p>
      {hasErrors && (
        <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-green-500 !border-[#0a0a0f] !w-3 !h-3"
      />
    </div>
  )
})

StartNode.displayName = 'StartNode'
