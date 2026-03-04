import React from 'react'

const TEMPLATES = [
  {
    name: 'Cita medica',
    description: 'Recopila nombre y telefono, agenda una cita, y despide.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola, bienvenido a la clinica. Soy tu asistente virtual, con gusto te ayudo a agendar tu cita.' } },
      { id: 'c-nombre', type: 'collectInput', position: { x: 300, y: 160 }, data: { variableName: 'nombre', variableType: 'text', prompt: 'A nombre de quien sera la cita?', retryMessage: 'No entendi tu nombre, puedes repetirlo?', maxRetries: 3 } },
      { id: 'c-tel', type: 'collectInput', position: { x: 300, y: 340 }, data: { variableName: 'telefono', variableType: 'phone', prompt: 'Me puedes dar tu numero de telefono?', retryMessage: 'Necesito un numero de telefono valido.', maxRetries: 3 } },
      { id: 'a-cita', type: 'action', position: { x: 300, y: 520 }, data: { actionType: 'schedule_appointment', parameters: { patient_name: '{{nombre}}' }, resultVariable: 'cita_resultado', onFailureMessage: 'Hubo un error al agendar, disculpa.' } },
      { id: 'end-1', type: 'end', position: { x: 300, y: 700 }, data: { message: 'Listo {{nombre}}, tu cita quedo agendada. Te confirmaremos al {{telefono}}. Hasta luego!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-nombre', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-nombre', target: 'c-tel', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'c-tel', target: 'a-cita', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'a-cita', target: 'end-1', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
    ],
  },
  {
    name: 'Atencion al cliente',
    description: 'Saluda, recopila consulta, busca informacion, y ofrece transferir.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola! Gracias por llamar. En que puedo ayudarte hoy?' } },
      { id: 'c-consulta', type: 'collectInput', position: { x: 300, y: 160 }, data: { variableName: 'consulta', variableType: 'text', prompt: 'Cuentame, cual es tu consulta?', retryMessage: 'No logre entenderte, puedes repetir?', maxRetries: 3 } },
      { id: 'a-buscar', type: 'action', position: { x: 300, y: 340 }, data: { actionType: 'search_knowledge', parameters: { query: '{{consulta}}' }, resultVariable: 'respuesta', onFailureMessage: 'No encontre informacion sobre eso.' } },
      { id: 'msg-resp', type: 'message', position: { x: 150, y: 520 }, data: { message: '{{respuesta}}', waitForResponse: true } },
      { id: 'c-mas', type: 'collectInput', position: { x: 150, y: 680 }, data: { variableName: 'necesita_mas', variableType: 'yes_no', prompt: 'Hay algo mas en lo que pueda ayudarte?', retryMessage: '', maxRetries: 1 } },
      { id: 'transfer-1', type: 'transfer', position: { x: 500, y: 520 }, data: { message: 'Te voy a transferir con un agente para que te ayude mejor.', transferNumber: '' } },
      { id: 'end-1', type: 'end', position: { x: 150, y: 860 }, data: { message: 'Fue un placer ayudarte. Hasta luego!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-consulta', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-consulta', target: 'a-buscar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'a-buscar', target: 'msg-resp', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'a-buscar', target: 'transfer-1', sourceHandle: 'failure', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'msg-resp', target: 'c-mas', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e6', source: 'c-mas', target: 'c-consulta', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4 },
      { id: 'e7', source: 'c-mas', target: 'end-1', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4 },
    ],
  },
  {
    name: 'Captura de leads',
    description: 'Recopila nombre, email y telefono, y guarda el contacto.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola! Me gustaria conocerte mejor para poder ayudarte. Me permites unos datos?' } },
      { id: 'c-nombre', type: 'collectInput', position: { x: 300, y: 160 }, data: { variableName: 'nombre', variableType: 'text', prompt: 'Como te llamas?', retryMessage: 'No entendi tu nombre.', maxRetries: 3 } },
      { id: 'c-email', type: 'collectInput', position: { x: 300, y: 340 }, data: { variableName: 'email', variableType: 'email', prompt: 'Me puedes dar tu correo electronico?', retryMessage: 'Necesito un correo valido con @.', maxRetries: 3 } },
      { id: 'c-tel', type: 'collectInput', position: { x: 300, y: 520 }, data: { variableName: 'telefono', variableType: 'phone', prompt: 'Y tu numero de telefono?', retryMessage: 'Necesito un telefono valido.', maxRetries: 3 } },
      { id: 'a-guardar', type: 'action', position: { x: 300, y: 700 }, data: { actionType: 'save_contact', parameters: { name: '{{nombre}}', email: '{{email}}', phone: '{{telefono}}' }, resultVariable: '', onFailureMessage: 'Hubo un error al guardar tus datos.' } },
      { id: 'end-1', type: 'end', position: { x: 300, y: 880 }, data: { message: 'Perfecto {{nombre}}, ya tengo tus datos. Nos pondremos en contacto contigo pronto!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-nombre', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-nombre', target: 'c-email', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'c-email', target: 'c-tel', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'c-tel', target: 'a-guardar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'a-guardar', target: 'end-1', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
    ],
  },
  {
    name: 'FAQ / Preguntas frecuentes',
    description: 'Recibe pregunta, busca en base de conocimientos, y responde.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola! Soy tu asistente. Preguntame lo que necesites sobre nuestros servicios.' } },
      { id: 'c-pregunta', type: 'collectInput', position: { x: 300, y: 160 }, data: { variableName: 'pregunta', variableType: 'text', prompt: 'Cual es tu pregunta?', retryMessage: 'No entendi, puedes repetir?', maxRetries: 2 } },
      { id: 'a-buscar', type: 'action', position: { x: 300, y: 340 }, data: { actionType: 'search_knowledge', parameters: { query: '{{pregunta}}' }, resultVariable: 'respuesta', onFailureMessage: 'No encontre informacion sobre eso.' } },
      { id: 'msg-resp', type: 'message', position: { x: 300, y: 520 }, data: { message: '{{respuesta}}', waitForResponse: true } },
      { id: 'c-otra', type: 'collectInput', position: { x: 300, y: 680 }, data: { variableName: 'otra_pregunta', variableType: 'yes_no', prompt: 'Tienes alguna otra pregunta?', retryMessage: '', maxRetries: 1 } },
      { id: 'end-1', type: 'end', position: { x: 500, y: 860 }, data: { message: 'Perfecto, fue un gusto ayudarte. Hasta luego!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-pregunta', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-pregunta', target: 'a-buscar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'a-buscar', target: 'msg-resp', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'msg-resp', target: 'c-otra', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'c-otra', target: 'c-pregunta', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4 },
      { id: 'e6', source: 'c-otra', target: 'end-1', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4 },
    ],
  },
]

const TEMPLATE_ICONS = {
  'Cita medica': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  ),
  'Atencion al cliente': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
  ),
  'Captura de leads': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  'FAQ / Preguntas frecuentes': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
}

export function FlowTemplates({ open, onClose, onSelect }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#12121a] border border-[#2a2a3e] rounded-xl w-[600px] max-h-[80vh] overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-[#2a2a3e]">
          <div>
            <h2 className="text-lg font-semibold text-[#e8e8f0]">Plantillas de flujo</h2>
            <p className="text-xs text-[#8888a0] mt-0.5">Elige una plantilla para empezar rapido</p>
          </div>
          <button
            onClick={onClose}
            className="text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-4 space-y-3 overflow-y-auto max-h-[60vh]">
          {TEMPLATES.map((tpl) => (
            <button
              key={tpl.name}
              onClick={() => {
                onSelect(tpl.nodes, tpl.edges)
                onClose()
              }}
              className="w-full flex items-start gap-4 p-4 rounded-lg border border-[#2a2a3e]
                         bg-[#0a0a0f] hover:border-[#00f0ff]/50 hover:bg-[#1a1a2e]
                         transition-colors text-left group"
            >
              <div className="text-[#00f0ff] mt-0.5 shrink-0">
                {TEMPLATE_ICONS[tpl.name] || TEMPLATE_ICONS['FAQ / Preguntas frecuentes']}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#e8e8f0] group-hover:text-[#00f0ff] transition-colors">
                  {tpl.name}
                </h3>
                <p className="text-xs text-[#8888a0] mt-1">{tpl.description}</p>
                <p className="text-[10px] text-[#555570] mt-1.5">
                  {tpl.nodes.length} nodos &middot; {tpl.edges.length} conexiones
                </p>
              </div>
            </button>
          ))}
        </div>
        <div className="p-4 border-t border-[#2a2a3e]">
          <button
            onClick={onClose}
            className="w-full py-2 text-sm text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
          >
            Empezar con canvas vacio
          </button>
        </div>
      </div>
    </div>
  )
}
