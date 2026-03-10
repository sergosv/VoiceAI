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
  {
    name: 'Inmobiliaria',
    description: 'Recopila tipo de propiedad, presupuesto y zona, busca opciones y agenda visita.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola, soy el asistente inmobiliario. Te ayudo a encontrar la propiedad ideal.' } },
      { id: 'cm-datos', type: 'collectMultiple', position: { x: 300, y: 180 }, data: { label: 'Datos de busqueda', fields: [{ name: 'tipo_propiedad', type: 'text', prompt: 'Que tipo de propiedad buscas? Casa, departamento, terreno...' }, { name: 'presupuesto', type: 'text', prompt: 'Cual es tu presupuesto aproximado?' }, { name: 'zona', type: 'text', prompt: 'En que zona o colonia te gustaria?' }], maxRetries: 3 } },
      { id: 'a-buscar', type: 'action', position: { x: 300, y: 380 }, data: { actionType: 'search_knowledge', parameters: { query: '{{tipo_propiedad}} {{presupuesto}} {{zona}}' }, resultVariable: 'resultados', onFailureMessage: 'No pude buscar en este momento.' } },
      { id: 'cond-found', type: 'condition', position: { x: 300, y: 560 }, data: { conditions: [{ variable: 'resultados', operator: 'not_empty', value: '', handleId: 'cond-found' }], defaultHandleId: 'default' } },
      { id: 'msg-ok', type: 'message', position: { x: 100, y: 720 }, data: { message: 'Tenemos opciones que podrian interesarte: {{resultados}}', waitForResponse: false } },
      { id: 'c-visita', type: 'collectInput', position: { x: 100, y: 880 }, data: { variableName: 'agendar_visita', variableType: 'yes_no', prompt: 'Te gustaria agendar una visita?', retryMessage: '', maxRetries: 1 } },
      { id: 'a-agendar', type: 'action', position: { x: 0, y: 1060 }, data: { actionType: 'schedule_appointment', parameters: { property_type: '{{tipo_propiedad}}', zone: '{{zona}}' }, resultVariable: '', onFailureMessage: 'No pude agendar, disculpa.' } },
      { id: 'end-ok', type: 'end', position: { x: 0, y: 1220 }, data: { message: 'Perfecto, tu visita queda agendada. Te contactaremos para confirmar. Hasta pronto!', hangup: true } },
      { id: 'end-wa', type: 'end', position: { x: 250, y: 1060 }, data: { message: 'Entendido, te enviaremos las opciones por WhatsApp. Hasta pronto!', hangup: true } },
      { id: 'msg-no', type: 'message', position: { x: 500, y: 720 }, data: { message: 'No encontramos opciones exactas para tu busqueda, pero un asesor puede ayudarte.', waitForResponse: false } },
      { id: 'end-no', type: 'end', position: { x: 500, y: 880 }, data: { message: 'Un asesor te contactara pronto. Gracias por tu interes!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'cm-datos', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'cm-datos', target: 'a-buscar', sourceHandle: 'default', animated: true, label: 'Siguiente', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'a-buscar', target: 'cond-found', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'cond-found', target: 'msg-ok', sourceHandle: 'cond-found', animated: true, label: 'resultados no vacio', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'cond-found', target: 'msg-no', sourceHandle: 'default', animated: true, label: 'default', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e6', source: 'msg-ok', target: 'c-visita', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e7', source: 'c-visita', target: 'a-agendar', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e8', source: 'c-visita', target: 'end-wa', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e9', source: 'a-agendar', target: 'end-ok', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e10', source: 'msg-no', target: 'end-no', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e11', source: 'a-buscar', target: 'msg-no', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
    ],
  },
  {
    name: 'Restaurante',
    description: 'Reservacion: recopila fecha, hora, comensales y nombre, agenda y confirma.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Bienvenido a nuestro restaurante! En que puedo ayudarte?' } },
      { id: 'c-reservar', type: 'collectInput', position: { x: 300, y: 180 }, data: { variableName: 'desea_reservar', variableType: 'yes_no', prompt: 'Deseas hacer una reservacion?', retryMessage: '', maxRetries: 1 } },
      { id: 'cm-reserva', type: 'collectMultiple', position: { x: 100, y: 360 }, data: { label: 'Datos de reservacion', fields: [{ name: 'fecha', type: 'date', prompt: 'Para que fecha seria la reservacion?' }, { name: 'hora', type: 'time', prompt: 'A que hora te gustaria llegar?' }, { name: 'comensales', type: 'number', prompt: 'Para cuantas personas?' }, { name: 'nombre', type: 'text', prompt: 'A nombre de quien sera la reservacion?' }], maxRetries: 3 } },
      { id: 'a-reservar', type: 'action', position: { x: 100, y: 580 }, data: { actionType: 'schedule_appointment', parameters: { date: '{{fecha}}', time: '{{hora}}', guests: '{{comensales}}', name: '{{nombre}}' }, resultVariable: '', onFailureMessage: 'No pude procesar la reservacion.' } },
      { id: 'end-reserva', type: 'end', position: { x: 100, y: 760 }, data: { message: 'Reservacion confirmada para {{nombre}}, {{fecha}} a las {{hora}} para {{comensales}} personas. Te esperamos!', hangup: true } },
      { id: 'c-consulta', type: 'collectInput', position: { x: 500, y: 360 }, data: { variableName: 'consulta', variableType: 'text', prompt: 'Cuentame, en que puedo ayudarte?', retryMessage: 'No entendi, puedes repetir?', maxRetries: 2 } },
      { id: 'a-buscar', type: 'action', position: { x: 500, y: 540 }, data: { actionType: 'search_knowledge', parameters: { query: '{{consulta}}' }, resultVariable: 'respuesta', onFailureMessage: 'No encontre informacion sobre eso.' } },
      { id: 'msg-resp', type: 'message', position: { x: 500, y: 720 }, data: { message: '{{respuesta}}', waitForResponse: false } },
      { id: 'end-info', type: 'end', position: { x: 500, y: 880 }, data: { message: 'Espero haberte ayudado. Te esperamos pronto!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-reservar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-reservar', target: 'cm-reserva', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'c-reservar', target: 'c-consulta', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'cm-reserva', target: 'a-reservar', sourceHandle: 'default', animated: true, label: 'Siguiente', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'a-reservar', target: 'end-reserva', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e6', source: 'c-consulta', target: 'a-buscar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e7', source: 'a-buscar', target: 'msg-resp', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e8', source: 'msg-resp', target: 'end-info', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e9', source: 'a-reservar', target: 'end-info', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e10', source: 'a-buscar', target: 'end-info', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
    ],
  },
  {
    name: 'Ecommerce',
    description: 'Estado de pedido: identifica consulta, busca orden o transfiere para devoluciones.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Hola! Bienvenido a nuestra tienda. En que puedo ayudarte?' } },
      { id: 'c-tipo', type: 'collectInput', position: { x: 300, y: 180 }, data: { variableName: 'tipo_consulta', variableType: 'text', prompt: 'Cuentame, que necesitas? Puedo ayudarte con pedidos, envios, devoluciones o informacion.', retryMessage: 'No entendi, puedes ser mas especifico?', maxRetries: 2 } },
      { id: 'cond-pedido', type: 'condition', position: { x: 300, y: 360 }, data: { conditions: [{ variable: 'tipo_consulta', operator: 'contains', value: 'pedido|orden|envio|paquete', handleId: 'cond-pedido' }], defaultHandleId: 'default' } },
      { id: 'c-orden', type: 'collectInput', position: { x: 80, y: 540 }, data: { variableName: 'numero_orden', variableType: 'text', prompt: 'Me puedes dar tu numero de orden o pedido?', retryMessage: 'Necesito el numero de orden para buscarlo.', maxRetries: 3 } },
      { id: 'a-buscar-orden', type: 'action', position: { x: 80, y: 720 }, data: { actionType: 'search_knowledge', parameters: { query: 'orden {{numero_orden}}' }, resultVariable: 'estado_orden', onFailureMessage: 'No pude encontrar esa orden.' } },
      { id: 'msg-estado', type: 'message', position: { x: 80, y: 900 }, data: { message: 'El estado de tu orden {{numero_orden}}: {{estado_orden}}', waitForResponse: false } },
      { id: 'end-orden', type: 'end', position: { x: 80, y: 1060 }, data: { message: 'Espero haberte ayudado. Si tienes otra consulta, no dudes en llamar!', hangup: true } },
      { id: 'cond-devol', type: 'condition', position: { x: 500, y: 540 }, data: { conditions: [{ variable: 'tipo_consulta', operator: 'contains', value: 'devol|cambio|regres', handleId: 'cond-devol' }], defaultHandleId: 'default' } },
      { id: 'msg-devol', type: 'message', position: { x: 380, y: 720 }, data: { message: 'Para devoluciones y cambios necesitas hablar con un agente especializado.', waitForResponse: false } },
      { id: 'transfer-1', type: 'transfer', position: { x: 380, y: 880 }, data: { message: 'Te transfiero con un agente de devoluciones.', transferNumber: '' } },
      { id: 'a-buscar-info', type: 'action', position: { x: 620, y: 720 }, data: { actionType: 'search_knowledge', parameters: { query: '{{tipo_consulta}}' }, resultVariable: 'info', onFailureMessage: 'No encontre informacion sobre eso.' } },
      { id: 'msg-info', type: 'message', position: { x: 620, y: 900 }, data: { message: '{{info}}', waitForResponse: false } },
      { id: 'end-info', type: 'end', position: { x: 620, y: 1060 }, data: { message: 'Gracias por contactarnos. Hasta luego!', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-tipo', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-tipo', target: 'cond-pedido', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'cond-pedido', target: 'c-orden', sourceHandle: 'cond-pedido', animated: true, label: 'pedido/orden', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'cond-pedido', target: 'cond-devol', sourceHandle: 'default', animated: true, label: 'default', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'c-orden', target: 'a-buscar-orden', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e6', source: 'a-buscar-orden', target: 'msg-estado', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e7', source: 'msg-estado', target: 'end-orden', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e8', source: 'cond-devol', target: 'msg-devol', sourceHandle: 'cond-devol', animated: true, label: 'devolucion', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e9', source: 'cond-devol', target: 'a-buscar-info', sourceHandle: 'default', animated: true, label: 'default', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e10', source: 'msg-devol', target: 'transfer-1', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e11', source: 'a-buscar-info', target: 'msg-info', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e12', source: 'msg-info', target: 'end-info', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e13', source: 'a-buscar-orden', target: 'end-orden', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e14', source: 'a-buscar-info', target: 'end-info', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
    ],
  },
  {
    name: 'Cobranza',
    description: 'Identifica al deudor, informa saldo, negocia pago o agenda seguimiento.',
    nodes: [
      { id: 'start-1', type: 'start', position: { x: 300, y: 30 }, data: { greeting: 'Buenos dias, llamo de parte de la empresa respecto a su cuenta pendiente.' } },
      { id: 'c-identidad', type: 'collectInput', position: { x: 300, y: 180 }, data: { variableName: 'confirma_identidad', variableType: 'yes_no', prompt: 'Estoy hablando con el titular de la cuenta?', retryMessage: '', maxRetries: 1 } },
      { id: 'msg-saldo', type: 'message', position: { x: 100, y: 360 }, data: { message: 'Le informo que su saldo pendiente es de {{monto}}. Es importante regularizar su situacion.', waitForResponse: false } },
      { id: 'c-pagar', type: 'collectInput', position: { x: 100, y: 540 }, data: { variableName: 'puede_pagar', variableType: 'yes_no', prompt: 'Tiene posibilidad de realizar el pago?', retryMessage: '', maxRetries: 1 } },
      { id: 'c-fecha', type: 'collectInput', position: { x: -50, y: 720 }, data: { variableName: 'fecha_pago', variableType: 'date', prompt: 'Para que fecha puede realizar el pago?', retryMessage: 'Necesito una fecha valida.', maxRetries: 3 } },
      { id: 'a-guardar', type: 'action', position: { x: -50, y: 900 }, data: { actionType: 'save_contact', parameters: { payment_date: '{{fecha_pago}}', status: 'compromiso_pago' }, resultVariable: '', onFailureMessage: 'Hubo un error al registrar.' } },
      { id: 'end-pago', type: 'end', position: { x: -50, y: 1080 }, data: { message: 'Queda registrado su compromiso de pago para el {{fecha_pago}}. Gracias por su atencion.', hangup: true } },
      { id: 'c-motivo', type: 'collectInput', position: { x: 250, y: 720 }, data: { variableName: 'motivo', variableType: 'text', prompt: 'Entiendo. Me puede comentar el motivo?', retryMessage: '', maxRetries: 1 } },
      { id: 'msg-entiendo', type: 'message', position: { x: 250, y: 900 }, data: { message: 'Entiendo su situacion. Vamos a agendar un seguimiento para buscar una solucion.', waitForResponse: false } },
      { id: 'a-seguimiento', type: 'action', position: { x: 250, y: 1060 }, data: { actionType: 'schedule_appointment', parameters: { reason: '{{motivo}}', status: 'seguimiento' }, resultVariable: '', onFailureMessage: 'No pude agendar el seguimiento.' } },
      { id: 'end-seguimiento', type: 'end', position: { x: 250, y: 1220 }, data: { message: 'Queda agendado su seguimiento. Le contactaremos nuevamente. Gracias.', hangup: true } },
      { id: 'msg-noident', type: 'message', position: { x: 500, y: 360 }, data: { message: 'Necesitamos verificar su identidad para continuar.', waitForResponse: false } },
      { id: 'end-noident', type: 'end', position: { x: 500, y: 520 }, data: { message: 'Le pedimos que se comunique con nosotros con una identificacion. Hasta luego.', hangup: true } },
    ],
    edges: [
      { id: 'e1', source: 'start-1', target: 'c-identidad', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e2', source: 'c-identidad', target: 'msg-saldo', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e3', source: 'c-identidad', target: 'msg-noident', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e4', source: 'msg-saldo', target: 'c-pagar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e5', source: 'c-pagar', target: 'c-fecha', sourceHandle: 'yes', animated: true, label: 'Si', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e6', source: 'c-pagar', target: 'c-motivo', sourceHandle: 'no', animated: true, label: 'No', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e7', source: 'c-fecha', target: 'a-guardar', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e8', source: 'a-guardar', target: 'end-pago', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e9', source: 'c-motivo', target: 'msg-entiendo', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e10', source: 'msg-entiendo', target: 'a-seguimiento', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e11', source: 'a-seguimiento', target: 'end-seguimiento', sourceHandle: 'success', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e12', source: 'msg-noident', target: 'end-noident', sourceHandle: 'default', animated: true, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e13', source: 'a-guardar', target: 'end-pago', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
      { id: 'e14', source: 'a-seguimiento', target: 'end-seguimiento', sourceHandle: 'failure', animated: true, label: 'Error', labelStyle: { fill: '#8888a0', fontSize: 11 }, labelBgStyle: { fill: '#12121a', fillOpacity: 0.9 }, labelBgPadding: [6, 3], labelBgBorderRadius: 4, markerEnd: { type: 'arrowclosed', color: '#555570', width: 16, height: 16 }, style: { stroke: '#555570' } },
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
  'Inmobiliaria': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  ),
  'Restaurante': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  'Ecommerce': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
    </svg>
  ),
  'Cobranza': (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
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
