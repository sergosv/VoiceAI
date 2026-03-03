import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

export const ConditionNode = memo(({ data, selected }) => {
  const conditions = data.conditions || []
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[200px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-purple-400 ring-2 ring-purple-400/30' : 'border-purple-400/50'}
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
        className="!bg-purple-400 !border-[#0a0a0f] !w-3 !h-3"
      />
      <div className="flex items-center gap-2 mb-2">
        <div className="w-3 h-3 rounded-full bg-purple-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-purple-400">
          Condicion
        </span>
      </div>
      <div className="space-y-1">
        {conditions.map((cond, i) => (
          <div key={i} className="text-xs text-[#8888a0] font-mono truncate">
            {cond.variable} {cond.operator} {cond.value || '""'}
          </div>
        ))}
        {conditions.length === 0 && (
          <p className="text-xs text-[#555570] italic">Sin condiciones</p>
        )}
      </div>
      {/* Un handle por cada condicion + default */}
      {conditions.map((cond, i) => (
        <Handle
          key={cond.handleId || `cond-${i}`}
          type="source"
          position={Position.Bottom}
          id={cond.handleId || `cond-${i}`}
          className="!bg-purple-400 !border-[#0a0a0f] !w-2.5 !h-2.5"
          style={{
            left: `${((i + 1) / (conditions.length + 2)) * 100}%`,
          }}
        />
      ))}
      <Handle
        type="source"
        position={Position.Bottom}
        id={data.defaultHandleId || 'default'}
        className="!bg-[#8888a0] !border-[#0a0a0f] !w-2.5 !h-2.5"
        style={{
          left: `${((conditions.length + 1) / (conditions.length + 2)) * 100}%`,
        }}
      />
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'
