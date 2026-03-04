import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const HANDLE_SPACING = 48 // Pixeles entre handles

export const ConditionNode = memo(({ data, selected }) => {
  const conditions = data.conditions || []
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0
  const label = data.label || ''

  // Calcular ancho mínimo basado en número de handles
  const totalHandles = conditions.length + 1 // +1 para default
  const minWidth = Math.max(200, totalHandles * HANDLE_SPACING + 32)

  return (
    <div
      className={`
        rounded-lg border-2 px-4 py-3 pb-6 shadow-lg relative
        ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-purple-400 ring-2 ring-purple-400/30' : 'border-purple-400/50'}
        bg-[#1a1a2e]
      `}
      style={{ minWidth: `${minWidth}px` }}
    >
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
          {label || 'Condicion'}
        </span>
      </div>
      <div className="space-y-1">
        {conditions.map((cond, i) => (
          <div key={i} className="text-xs text-[#8888a0] font-mono truncate" title={`${cond.variable} ${cond.operator} ${cond.value || '""'}`}>
            {cond.variable} {cond.operator} {cond.value || '""'}
          </div>
        ))}
        {conditions.length === 0 && (
          <p className="text-xs text-[#555570] italic">Sin condiciones</p>
        )}
      </div>
      {/* Handles con espaciado fijo para evitar amontonamiento */}
      {conditions.map((cond, i) => {
        const offset = (i + 1) * HANDLE_SPACING
        return (
          <React.Fragment key={cond.handleId || `cond-${i}`}>
            <Handle
              type="source"
              position={Position.Bottom}
              id={cond.handleId || `cond-${i}`}
              className="!bg-purple-400 !border-[#0a0a0f] !w-2.5 !h-2.5"
              style={{ left: `${offset}px` }}
            />
            <span
              className="absolute text-purple-400 pointer-events-none whitespace-nowrap max-w-[44px] truncate text-center"
              style={{
                fontSize: '8px',
                bottom: '2px',
                left: `${offset}px`,
                transform: 'translateX(-50%)',
              }}
              title={`${cond.variable} ${cond.operator} ${cond.value || '""'}`}
            >
              {cond.variable || '?'}
            </span>
          </React.Fragment>
        )
      })}
      {(() => {
        const defaultOffset = (conditions.length + 1) * HANDLE_SPACING
        return (
          <>
            <Handle
              type="source"
              position={Position.Bottom}
              id={data.defaultHandleId || 'default'}
              className="!bg-[#8888a0] !border-[#0a0a0f] !w-2.5 !h-2.5"
              style={{ left: `${defaultOffset}px` }}
            />
            <span
              className="absolute text-[#8888a0] pointer-events-none"
              style={{
                fontSize: '8px',
                bottom: '2px',
                left: `${defaultOffset}px`,
                transform: 'translateX(-50%)',
              }}
            >
              default
            </span>
          </>
        )
      })()}
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'
