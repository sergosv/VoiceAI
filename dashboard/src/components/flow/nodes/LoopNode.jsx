import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const OP_LABELS = {
  equals: '==',
  not_equals: '!=',
  contains: '~',
  not_empty: '!vacio',
  empty: 'vacio',
  gt: '>',
  lt: '<',
}

export const LoopNode = memo(({ data, selected }) => {
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0
  const cond = data.condition || {}

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[200px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-violet-500 ring-2 ring-violet-500/30' : 'border-violet-500/50'}
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
        className="!bg-violet-500 !border-[#0a0a0f] !w-3 !h-3"
      />
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-3.5 h-3.5 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        <span className="text-xs font-bold uppercase tracking-wider text-violet-500">
          {data.label || 'Repetir'}
        </span>
        <span className="text-[10px] bg-violet-500/20 text-violet-300 px-1.5 py-0.5 rounded">
          max {data.maxIterations || 5}
        </span>
      </div>
      {cond.variable ? (
        <p className="text-xs text-[#8888a0] font-mono truncate" title={`${cond.variable} ${cond.operator} ${cond.value || '""'}`}>
          {cond.variable} {OP_LABELS[cond.operator] || cond.operator} {cond.value || '""'}
        </p>
      ) : (
        <p className="text-xs text-[#555570] italic">Sin condicion</p>
      )}
      {hasErrors && (
        <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        id="loop"
        className="!bg-violet-500 !border-[#0a0a0f] !w-3 !h-3"
        style={{ left: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="exit"
        className="!bg-emerald-400 !border-[#0a0a0f] !w-3 !h-3"
        style={{ left: '70%' }}
      />
      <div className="flex justify-between mt-2 text-[10px] text-[#8888a0]">
        <span className="text-violet-400">Repetir</span>
        <span className="text-emerald-400">Salir</span>
      </div>
    </div>
  )
})

LoopNode.displayName = 'LoopNode'
