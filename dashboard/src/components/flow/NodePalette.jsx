import React from 'react'

const PALETTE_ITEMS = [
  { type: 'message', label: 'Mensaje', color: 'bg-blue-400', desc: 'Enviar mensaje' },
  { type: 'collectInput', label: 'Recopilar', color: 'bg-amber-400', desc: 'Pedir dato' },
  { type: 'condition', label: 'Condicion', color: 'bg-purple-400', desc: 'Evaluar variable' },
  { type: 'action', label: 'Accion', color: 'bg-[#00f0ff]', desc: 'Ejecutar tool' },
  { type: 'transfer', label: 'Transferir', color: 'bg-orange-400', desc: 'Transferir llamada' },
  { type: 'wait', label: 'Espera', color: 'bg-gray-400', desc: 'Pausa en el flujo' },
  { type: 'end', label: 'Fin', color: 'bg-red-400', desc: 'Terminar flujo' },
]

export function NodePalette() {
  const onDragStart = (e, nodeType) => {
    e.dataTransfer.setData('application/reactflow', nodeType)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="w-[200px] bg-[#12121a] border-r border-[#2a2a3e] p-4 flex flex-col gap-2 overflow-y-auto">
      <h3 className="text-xs font-bold uppercase tracking-wider text-[#8888a0] mb-2">
        Nodos
      </h3>
      {PALETTE_ITEMS.map((item) => (
        <div
          key={item.type}
          className="flex items-center gap-3 p-3 rounded-lg border border-[#2a2a3e] bg-[#1a1a2e]
                     cursor-grab hover:border-[#555570] transition-colors select-none"
          draggable
          onDragStart={(e) => onDragStart(e, item.type)}
        >
          <div className={`w-3 h-3 rounded-full ${item.color} shrink-0`} />
          <div>
            <p className="text-sm text-[#e8e8f0] font-medium">{item.label}</p>
            <p className="text-[10px] text-[#555570]">{item.desc}</p>
          </div>
        </div>
      ))}
      <div className="mt-4 text-[10px] text-[#555570] leading-relaxed">
        Arrastra los nodos al canvas para construir tu flujo de conversacion.
        El nodo Inicio se crea automaticamente.
      </div>
    </div>
  )
}
