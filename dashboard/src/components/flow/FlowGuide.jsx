import React, { useState } from 'react'

const GUIDE_SECTIONS = [
  {
    id: 'overview',
    title: 'Como funciona',
    icon: '?',
    color: '#00f0ff',
    content: (
      <>
        <p>
          El Flow Builder te permite disenar conversaciones paso a paso en lugar
          de depender solo del system prompt. El agente sigue el flujo que
          construyas, nodo por nodo.
        </p>
        <h4>Conceptos clave</h4>
        <ul>
          <li><strong>Nodos</strong> — Cada paso de la conversacion (saludar, preguntar, decidir, etc.)</li>
          <li><strong>Conexiones</strong> — Las flechas que unen nodos y definen el orden</li>
          <li><strong>Variables</strong> — Datos que el usuario proporciona y que puedes reutilizar con <code>{'{{nombre}}'}</code></li>
        </ul>
        <h4>Flujo basico</h4>
        <ol>
          <li>Arrastra nodos desde la paleta izquierda al canvas</li>
          <li>Conecta los nodos arrastrando desde un punto de salida a uno de entrada</li>
          <li>Selecciona cada nodo para configurarlo en el panel derecho</li>
          <li>Usa "Probar flujo" para verificar sin guardar</li>
          <li>Guarda cuando estes satisfecho</li>
        </ol>
      </>
    ),
  },
  {
    id: 'start',
    title: 'Inicio',
    icon: 'S',
    color: '#22c55e',
    content: (
      <>
        <p>
          El primer nodo de todo flujo. Define como saluda el agente cuando
          contesta la llamada.
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Saludo inicial</strong> — Lo primero que dice el agente. Ej: "Hola, bienvenido a Clinica Dental. En que puedo ayudarte?"</li>
          <li><strong>Inyectar datos del llamante</strong> — Activa la variable <code>{'{{caller_number}}'}</code> para usar el telefono del que llama</li>
        </ul>
        <h4>Reglas</h4>
        <ul>
          <li>Solo puede haber UN nodo de Inicio por flujo</li>
          <li>No se puede eliminar ni duplicar</li>
          <li>Debe tener al menos una conexion de salida</li>
        </ul>
      </>
    ),
  },
  {
    id: 'message',
    title: 'Mensaje',
    icon: 'M',
    color: '#60a5fa',
    content: (
      <>
        <p>
          Envia un mensaje al usuario. Puede ser informativo (solo habla) o
          conversacional (habla y espera respuesta).
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Mensaje</strong> — El texto que el agente dice. Soporta variables: <code>{'{{nombre}}'}</code></li>
          <li><strong>Esperar respuesta</strong> — Si esta activo, el agente espera que el usuario conteste antes de avanzar al siguiente nodo</li>
        </ul>
        <h4>Ejemplo</h4>
        <div className="example">
          Mensaje: "Perfecto {'{{nombre}}'}, dejame buscar disponibilidad para ti."<br/>
          Esperar respuesta: No (es informativo, avanza de inmediato)
        </div>
      </>
    ),
  },
  {
    id: 'collectInput',
    title: 'Recopilar dato',
    icon: 'R',
    color: '#fbbf24',
    content: (
      <>
        <p>
          Pide un dato especifico al usuario y lo guarda en una variable
          que puedes usar despues en otros nodos.
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Nombre de variable</strong> — Como se llama el dato. Ej: <code>nombre</code>, <code>telefono</code>, <code>fecha_cita</code></li>
          <li><strong>Tipo de dato</strong> — Texto, Telefono, Email, Fecha, Hora, Numero, Si/No</li>
          <li><strong>Pregunta al usuario</strong> — Lo que el agente dice para pedir el dato. Ej: "Me puedes dar tu nombre completo?"</li>
          <li><strong>Mensaje de reintento</strong> — Si el usuario da una respuesta invalida (ej: texto cuando pides un telefono)</li>
          <li><strong>Reintentos maximos</strong> — Cuantas veces insistir antes de seguir por la ruta de "Max reintentos"</li>
        </ul>
        <h4>Salidas del nodo</h4>
        <ul>
          <li><strong>Salida principal</strong> (abajo) — Cuando captura el dato exitosamente</li>
          <li><strong>Si / No</strong> — Solo si el tipo es "Si/No", genera dos salidas</li>
          <li><strong>Max reintentos</strong> — Si falla todas las veces, sale por aqui</li>
        </ul>
        <h4>Ejemplo</h4>
        <div className="example">
          Variable: <code>nombre</code> (Texto)<br/>
          Pregunta: "Me puedes dar tu nombre completo por favor?"<br/>
          Reintento: "Disculpa, no escuche bien. Me repites tu nombre?"<br/>
          <br/>
          Despues puedes usar <code>{'{{nombre}}'}</code> en cualquier otro nodo.
        </div>
      </>
    ),
  },
  {
    id: 'condition',
    title: 'Condicion',
    icon: 'C',
    color: '#a78bfa',
    content: (
      <>
        <p>
          Evalua el valor de una variable y dirige el flujo por diferentes
          caminos segun el resultado. Es como un "if/else" para la conversacion.
        </p>
        <h4>Como funciona</h4>
        <ol>
          <li>Primero necesitas un nodo "Recopilar dato" antes, que defina la variable</li>
          <li>En la Condicion, seleccionas esa variable</li>
          <li>Eliges un operador (igual a, contiene, mayor que, etc.)</li>
          <li>Defines el valor a comparar</li>
          <li>Cada condicion genera una salida que puedes conectar a otro nodo</li>
        </ol>
        <h4>Operadores disponibles</h4>
        <ul>
          <li><strong>Igual a</strong> — El valor es exactamente ese</li>
          <li><strong>Diferente de</strong> — El valor NO es ese</li>
          <li><strong>Contiene</strong> — El texto incluye esa palabra</li>
          <li><strong>No vacio</strong> — La variable tiene algun valor</li>
          <li><strong>Vacio</strong> — La variable no tiene valor</li>
          <li><strong>Mayor que / Menor que</strong> — Para comparaciones numericas</li>
        </ul>
        <h4>La salida "default"</h4>
        <p>
          Si ninguna condicion se cumple, el flujo sigue por la conexion "default".
          Siempre conecta la salida default a algo para que no se atore.
        </p>
        <h4>Ejemplo practico</h4>
        <div className="example">
          <strong>Escenario:</strong> Preguntas "Quieres agendar cita?" con tipo Si/No, variable: <code>quiere_cita</code><br/><br/>
          <strong>Condicion:</strong><br/>
          - Variable: <code>quiere_cita</code><br/>
          - Operador: Igual a<br/>
          - Valor: <code>yes</code><br/><br/>
          <strong>Conexiones:</strong><br/>
          - Condicion 1 (quiere_cita = yes) → nodo "Agendar cita"<br/>
          - Default → nodo "Hay algo mas en que pueda ayudarte?"
        </div>
        <h4>Tip: variables Si/No</h4>
        <p>
          Cuando usas "Recopilar dato" con tipo Si/No, la variable se guarda como
          <code>yes</code> o <code>no</code> (en ingles). Asi que en la condicion
          compara con <code>yes</code> o <code>no</code>.
        </p>
      </>
    ),
  },
  {
    id: 'action',
    title: 'Accion',
    icon: 'A',
    color: '#00f0ff',
    content: (
      <>
        <p>
          Ejecuta una herramienta o API. Por ejemplo: buscar en la base de
          conocimientos, agendar una cita, enviar un WhatsApp, o llamar una API externa.
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Tipo de accion</strong> — Selecciona la herramienta a usar</li>
          <li><strong>Variable de resultado</strong> — Nombre de variable donde se guarda la respuesta (para usarla despues)</li>
          <li><strong>Parametros</strong> — Pares clave/valor que necesita la herramienta. Puedes usar <code>{'{{variable}}'}</code></li>
          <li><strong>Mensaje si falla</strong> — Lo que dice el agente si la herramienta falla</li>
        </ul>
        <h4>Salidas del nodo</h4>
        <ul>
          <li><strong>OK</strong> — La accion se ejecuto correctamente</li>
          <li><strong>Error</strong> — La accion fallo (siempre conecta esta salida)</li>
        </ul>
        <h4>Acciones disponibles</h4>
        <ul>
          <li><strong>Buscar en base de conocimientos</strong> — Busca en los documentos del agente</li>
          <li><strong>Agendar cita</strong> — Crea una cita con nombre, fecha y hora</li>
          <li><strong>Enviar WhatsApp</strong> — Manda un mensaje al usuario</li>
          <li><strong>Guardar contacto</strong> — Guarda datos del contacto en el CRM</li>
          <li><strong>Transferir a humano</strong> — Pasa la llamada a una persona</li>
          <li><strong>MCP Tools / APIs</strong> — Herramientas externas configuradas</li>
        </ul>
        <h4>Ejemplo</h4>
        <div className="example">
          Accion: Agendar cita<br/>
          Parametros:<br/>
          - patient_name → <code>{'{{nombre}}'}</code><br/>
          - date → <code>{'{{fecha}}'}</code><br/>
          - time → <code>{'{{hora}}'}</code><br/>
          Variable resultado: <code>cita_resultado</code>
        </div>
      </>
    ),
  },
  {
    id: 'transfer',
    title: 'Transferir',
    icon: 'T',
    color: '#fb923c',
    content: (
      <>
        <p>
          Transfiere la llamada a un numero telefonico o agente humano.
          Es un nodo terminal (no tiene salida).
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Mensaje antes de transferir</strong> — Lo que dice antes de pasar la llamada</li>
          <li><strong>Numero de transferencia</strong> — Numero SIP o telefonico (+52...)</li>
        </ul>
      </>
    ),
  },
  {
    id: 'wait',
    title: 'Espera',
    icon: 'W',
    color: '#9ca3af',
    content: (
      <>
        <p>
          Hace una pausa de N segundos antes de continuar al siguiente nodo.
          Util para dar tiempo a que se procese algo.
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Segundos de espera</strong> — Cuantos segundos pausar</li>
          <li><strong>Mensaje durante espera</strong> — Opcional. Ej: "Un momento por favor..."</li>
        </ul>
      </>
    ),
  },
  {
    id: 'end',
    title: 'Fin',
    icon: 'F',
    color: '#f87171',
    content: (
      <>
        <p>
          Termina la conversacion. Es un nodo terminal (no tiene salida).
        </p>
        <h4>Campos</h4>
        <ul>
          <li><strong>Mensaje de despedida</strong> — Lo ultimo que dice el agente</li>
          <li><strong>Colgar llamada</strong> — Si se activa, cuelga automaticamente despues del mensaje</li>
        </ul>
      </>
    ),
  },
  {
    id: 'variables',
    title: 'Variables',
    icon: 'V',
    color: '#00f0ff',
    content: (
      <>
        <p>
          Las variables son datos que recopilas del usuario y reutilizas en
          otros nodos. Se escriben asi: <code>{'{{nombre_variable}}'}</code>
        </p>
        <h4>Como se crean</h4>
        <ul>
          <li><strong>Recopilar dato</strong> — El nombre de variable que pongas se vuelve disponible</li>
          <li><strong>Accion</strong> — La "Variable de resultado" guarda la respuesta de la herramienta</li>
          <li><strong>Inicio</strong> — Si activas "Inyectar datos del llamante", tienes <code>{'{{caller_number}}'}</code></li>
        </ul>
        <h4>Donde se usan</h4>
        <p>
          En cualquier campo de texto de cualquier nodo posterior:
        </p>
        <div className="example">
          "Perfecto {'{{nombre}}'}, tu cita quedo para el {'{{fecha}}'} a las {'{{hora}}'}."
        </div>
        <h4>Tip</h4>
        <p>
          En el panel de Propiedades (derecha), abajo aparece la seccion
          "Variables del flujo" con todas las disponibles. Click en "copiar" para
          insertar <code>{'{{variable}}'}</code> en el portapapeles.
        </p>
      </>
    ),
  },
  {
    id: 'shortcuts',
    title: 'Atajos de teclado',
    icon: 'K',
    color: '#8888a0',
    content: (
      <>
        <ul>
          <li><code>Ctrl+S</code> — Guardar flujo</li>
          <li><code>Ctrl+Z</code> — Deshacer</li>
          <li><code>Ctrl+Y</code> — Rehacer</li>
          <li><code>Ctrl+C</code> — Copiar nodo(s) seleccionado(s)</li>
          <li><code>Ctrl+V</code> — Pegar nodo(s)</li>
          <li><code>Ctrl+D</code> — Duplicar nodo seleccionado</li>
          <li><code>Ctrl+F</code> — Buscar nodos</li>
          <li><code>Delete</code> — Eliminar nodo o conexion seleccionada</li>
          <li><code>Escape</code> — Cerrar busqueda</li>
        </ul>
        <h4>Otras acciones</h4>
        <ul>
          <li><strong>Arrastrar desde paleta</strong> — Agrega nodos al canvas</li>
          <li><strong>Click + arrastrar en canvas</strong> — Seleccionar multiples nodos</li>
          <li><strong>Scroll / pinch</strong> — Zoom in/out</li>
        </ul>
      </>
    ),
  },
]

export function FlowGuide({ open, onClose }) {
  const [activeSection, setActiveSection] = useState('overview')

  if (!open) return null

  const section = GUIDE_SECTIONS.find(s => s.id === activeSection) || GUIDE_SECTIONS[0]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-3xl h-[80vh] max-h-[700px] bg-[#12121a] border border-[#2a2a3e] rounded-2xl shadow-2xl flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-48 shrink-0 border-r border-[#2a2a3e] py-4 overflow-y-auto">
          <h3 className="px-4 text-xs font-bold uppercase tracking-wider text-[#8888a0] mb-3">
            Guia de nodos
          </h3>
          {GUIDE_SECTIONS.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className={`w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition-colors ${
                activeSection === s.id
                  ? 'bg-[#252540] text-[#e8e8f0]'
                  : 'text-[#8888a0] hover:bg-[#1a1a2e] hover:text-[#e8e8f0]'
              }`}
            >
              <span
                className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold shrink-0"
                style={{ backgroundColor: s.color + '20', color: s.color }}
              >
                {s.icon}
              </span>
              {s.title}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a3e] shrink-0">
            <h2 className="text-lg font-semibold text-[#e8e8f0] flex items-center gap-2">
              <span
                className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
                style={{ backgroundColor: section.color + '20', color: section.color }}
              >
                {section.icon}
              </span>
              {section.title}
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-5 flow-guide-content">
            {section.content}
          </div>
        </div>
      </div>
    </div>
  )
}
