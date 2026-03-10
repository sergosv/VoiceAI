import React, { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

const TYPE_LABELS = {
  text: 'Txt',
  phone: 'Tel',
  email: 'Email',
  date: 'Fecha',
  time: 'Hora',
  number: 'Num',
  yes_no: 'S/N',
}

export const CollectMultipleNode = memo(({ data, selected }) => {
  const errors = data._validationErrors || []
  const hasErrors = errors.length > 0
  const fields = data.fields || []

  return (
    <div className={`
      rounded-lg border-2 px-4 py-3 min-w-[200px] shadow-lg relative
      ${hasErrors ? 'border-red-500 ring-2 ring-red-500/30' : selected ? 'border-teal-500 ring-2 ring-teal-500/30' : 'border-teal-500/50'}
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
        className="!bg-teal-500 !border-[#0a0a0f] !w-3 !h-3"
      />
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-3.5 h-3.5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
        <span className="text-xs font-bold uppercase tracking-wider text-teal-500">
          {data.label || 'Datos del cliente'}
        </span>
      </div>
      {fields.length > 0 ? (
        <div className="space-y-0.5">
          {fields.slice(0, 4).map((field, i) => (
            <div key={i} className="text-xs text-[#8888a0] truncate">
              <span className="text-teal-400 font-mono">{field.name || '?'}</span>
              <span className="text-[#555570] ml-1">({TYPE_LABELS[field.type] || field.type || 'Txt'})</span>
            </div>
          ))}
          {fields.length > 4 && (
            <p className="text-[10px] text-[#555570]">+{fields.length - 4} mas...</p>
          )}
        </div>
      ) : (
        <p className="text-xs text-[#555570] italic">Sin campos</p>
      )}
      {hasErrors && (
        <p className="text-[10px] text-red-400 mt-1 truncate">{errors[0]}</p>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        id="default"
        className="!bg-teal-500 !border-[#0a0a0f] !w-3 !h-3"
      />
    </div>
  )
})

CollectMultipleNode.displayName = 'CollectMultipleNode'
