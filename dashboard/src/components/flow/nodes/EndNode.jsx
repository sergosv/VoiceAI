import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

export const EndNode = memo(({ data, selected }) => {
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[180px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-red-400 ring-2 ring-red-400/30' : 'border-red-400/50'}
      bg-[#1a1a2e]
    `}>
      {hasErrors && (
        <div className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
          {errors.length}
        </div>
      )}
      {data.comment && (
        <div className="absolute -top-2 -left-2 w-5 h-5 bg-amber-500/80 rounded-full flex items-center justify-center" title={data.comment}>
          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
          </svg>
        </div>
      )}
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-red-400 !border-[#0a0a0f] !w-3 !h-3"
      />
      <div className="flex items-center gap-2 mb-2">
        <div className="w-3 h-3 rounded-full bg-red-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-red-400">{data.label || 'Fin'}</span>
        {data.hangup && (
          <span className="text-[10px] bg-red-400/20 text-red-300 px-1.5 py-0.5 rounded">
            colgar
          </span>
        )}
      </div>
      <p className="text-sm text-[#e8e8f0] line-clamp-2">
        {data.message || 'Despedida...'}
      </p>
      {hasErrors && (
        <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
      )}
    </div>
  )
})

EndNode.displayName = 'EndNode'
