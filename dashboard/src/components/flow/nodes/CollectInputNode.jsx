import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const TYPE_LABELS = {
  text: 'Texto',
  phone: 'Telefono',
  email: 'Email',
  date: 'Fecha',
  time: 'Hora',
  number: 'Numero',
  yes_no: 'Si/No',
}

export const CollectInputNode = memo(({ data, selected }) => {
  const isYesNo = data.variableType === 'yes_no'
  const hasTimeout = data.timeout && data.timeout > 0
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[180px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-amber-400 ring-2 ring-amber-400/30' : 'border-amber-400/50'}
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
        className="!bg-amber-400 !border-[#0a0a0f] !w-3 !h-3"
      />
      <div className="flex items-center gap-2 mb-2">
        <div className="w-3 h-3 rounded-full bg-amber-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
          {data.label || 'Recopilar'}
        </span>
        <span className="text-[10px] bg-amber-400/20 text-amber-300 px-1.5 py-0.5 rounded">
          {TYPE_LABELS[data.variableType] || data.variableType || 'Texto'}
        </span>
      </div>
      {data.variableName && (
        <p className="text-xs text-[#8888a0] mb-1 font-mono">{`{${data.variableName}}`}</p>
      )}
      <p className="text-sm text-[#e8e8f0] line-clamp-2">
        {data.prompt || 'Pregunta...'}
      </p>
      {hasErrors && (
        <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
      )}
      {isYesNo ? (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="yes"
            className="!bg-green-400 !border-[#0a0a0f] !w-3 !h-3"
            style={{ left: hasTimeout ? '20%' : '30%' }}
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="no"
            className="!bg-red-400 !border-[#0a0a0f] !w-3 !h-3"
            style={{ left: hasTimeout ? '50%' : '70%' }}
          />
          {hasTimeout && (
            <Handle
              type="source"
              position={Position.Bottom}
              id="timeout"
              className="!bg-gray-400 !border-[#0a0a0f] !w-3 !h-3"
              style={{ left: '80%' }}
            />
          )}
          <div className="flex justify-between mt-2 text-[10px] text-[#8888a0]">
            <span>Si</span>
            <span>No</span>
            {hasTimeout && <span className="text-gray-400">Timeout</span>}
          </div>
        </>
      ) : (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="default"
            className="!bg-amber-400 !border-[#0a0a0f] !w-3 !h-3"
            style={{ left: hasTimeout ? '20%' : '35%' }}
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="maxRetries"
            className="!bg-red-400 !border-[#0a0a0f] !w-3 !h-3"
            style={{ left: hasTimeout ? '50%' : '65%' }}
          />
          {hasTimeout && (
            <Handle
              type="source"
              position={Position.Bottom}
              id="timeout"
              className="!bg-gray-400 !border-[#0a0a0f] !w-3 !h-3"
              style={{ left: '80%' }}
            />
          )}
          <div className="flex justify-between mt-2 text-[10px] text-[#8888a0]">
            <span>OK</span>
            <span>Max reintentos</span>
            {hasTimeout && <span className="text-gray-400">Timeout</span>}
          </div>
        </>
      )}
    </div>
  )
})

CollectInputNode.displayName = 'CollectInputNode'
