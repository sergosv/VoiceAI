import React from 'react'

const VARIABLE_TYPES = [
  { value: 'text', label: 'Texto' },
  { value: 'phone', label: 'Telefono' },
  { value: 'email', label: 'Email' },
  { value: 'date', label: 'Fecha' },
  { value: 'time', label: 'Hora' },
  { value: 'number', label: 'Numero' },
  { value: 'yes_no', label: 'Si/No' },
]

const OPERATORS = [
  { value: 'equals', label: 'Igual a' },
  { value: 'not_equals', label: 'Diferente de' },
  { value: 'contains', label: 'Contiene' },
  { value: 'not_empty', label: 'No vacio' },
  { value: 'empty', label: 'Vacio' },
  { value: 'gt', label: 'Mayor que' },
  { value: 'lt', label: 'Menor que' },
]

const ACTION_TYPES = [
  { value: 'search_knowledge', label: 'Buscar en base de conocimientos' },
  { value: 'schedule_appointment', label: 'Agendar cita' },
  { value: 'send_whatsapp', label: 'Enviar WhatsApp' },
  { value: 'save_contact', label: 'Guardar contacto' },
  { value: 'transfer_to_human', label: 'Transferir a humano' },
]

function Label({ children }) {
  return <label className="block text-xs font-medium text-[#8888a0] mb-1">{children}</label>
}

function TextArea({ value, onChange, placeholder, rows = 3 }) {
  return (
    <textarea
      className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                 text-sm text-[#e8e8f0] placeholder-[#555570] resize-none
                 focus:outline-none focus:border-[#00f0ff]/50"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
    />
  )
}

function Input({ value, onChange, placeholder, type = 'text' }) {
  return (
    <input
      type={type}
      className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                 text-sm text-[#e8e8f0] placeholder-[#555570]
                 focus:outline-none focus:border-[#00f0ff]/50"
      value={value || ''}
      onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
      placeholder={placeholder}
    />
  )
}

function Select({ value, onChange, options }) {
  return (
    <select
      className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#00f0ff]/50"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}

function Checkbox({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked || false}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 rounded border-[#2a2a3e] bg-[#0a0a0f] text-[#00f0ff]
                   focus:ring-[#00f0ff]/50 focus:ring-offset-0"
      />
      <span className="text-sm text-[#e8e8f0]">{label}</span>
    </label>
  )
}

export function PropertiesPanel({ selectedNode, onNodeDataChange, mcpTools = [], apiTools = [], nodes = [] }) {
  if (!selectedNode) {
    return (
      <div className="w-[320px] bg-[#12121a] border-l border-[#2a2a3e] p-4 flex items-center justify-center">
        <p className="text-sm text-[#555570]">Selecciona un nodo para editar</p>
      </div>
    )
  }

  const { type, data } = selectedNode
  const update = (key, value) => onNodeDataChange(selectedNode.id, key, value)

  return (
    <div className="w-[320px] bg-[#12121a] border-l border-[#2a2a3e] p-4 overflow-y-auto">
      <h3 className="text-xs font-bold uppercase tracking-wider text-[#8888a0] mb-4">
        Propiedades
      </h3>

      <div className="mb-4">
        <Label>Etiqueta del nodo</Label>
        <Input
          value={data.label}
          onChange={(v) => update('label', v)}
          placeholder={type === 'start' ? 'Inicio' : type === 'end' ? 'Fin' : type}
        />
      </div>

      {type === 'start' && (
        <div className="space-y-3">
          <div>
            <Label>Saludo inicial</Label>
            <TextArea
              value={data.greeting}
              onChange={(v) => update('greeting', v)}
              placeholder="Hola, bienvenido..."
              rows={4}
            />
          </div>
          <Checkbox
            checked={data.injectCallerInfo}
            onChange={(v) => update('injectCallerInfo', v)}
            label="Inyectar datos del llamante"
          />
          {data.injectCallerInfo && (
            <p className="text-[10px] text-[#555570] ml-6">
              {'Variables disponibles: {{caller_number}}'}
            </p>
          )}
        </div>
      )}

      {type === 'message' && (
        <div className="space-y-3">
          <div>
            <Label>Mensaje</Label>
            <TextArea
              value={data.message}
              onChange={(v) => update('message', v)}
              placeholder="Escribe el mensaje..."
              rows={4}
            />
            <p className="text-[10px] text-[#555570] mt-1">
              {'Usa {{variable}} para insertar datos recopilados'}
            </p>
          </div>
          <Checkbox
            checked={data.waitForResponse}
            onChange={(v) => update('waitForResponse', v)}
            label="Esperar respuesta del usuario"
          />
        </div>
      )}

      {type === 'collectInput' && (
        <div className="space-y-3">
          <div>
            <Label>Nombre de variable</Label>
            <Input
              value={data.variableName}
              onChange={(v) => update('variableName', v)}
              placeholder="nombre, telefono, email..."
            />
          </div>
          <div>
            <Label>Tipo de dato</Label>
            <Select
              value={data.variableType}
              onChange={(v) => update('variableType', v)}
              options={VARIABLE_TYPES}
            />
          </div>
          <div>
            <Label>Pregunta al usuario</Label>
            <TextArea
              value={data.prompt}
              onChange={(v) => update('prompt', v)}
              placeholder="Como te llamas?"
            />
          </div>
          <div>
            <Label>Mensaje de reintento</Label>
            <TextArea
              value={data.retryMessage}
              onChange={(v) => update('retryMessage', v)}
              placeholder="No entendi, puedes repetirlo?"
              rows={2}
            />
          </div>
          <div>
            <Label>Reintentos maximos</Label>
            <Input
              type="number"
              value={data.maxRetries}
              onChange={(v) => update('maxRetries', v)}
              placeholder="3"
            />
          </div>
          {data.variableType === 'yes_no' && (
            <div>
              <Label>Palabras de Si adicionales</Label>
              <Input
                value={data.yesKeywords}
                onChange={(v) => update('yesKeywords', v)}
                placeholder="dale, perfecto, afirmativo"
              />
              <p className="text-[10px] text-[#555570] mt-1">
                Separadas por coma. Ya incluye: si, yes, claro, ok, sale, va
              </p>
            </div>
          )}
          <div>
            <Label>Timeout (seg)</Label>
            <Input
              type="number"
              value={data.timeout}
              onChange={(v) => update('timeout', v || null)}
              placeholder="Sin timeout"
            />
            <p className="text-[10px] text-[#555570] mt-1">
              Si el usuario no responde en este tiempo, se sigue por la ruta "Timeout"
            </p>
          </div>
        </div>
      )}

      {type === 'condition' && (
        <ConditionProperties
          conditions={data.conditions || []}
          defaultHandleId={data.defaultHandleId || 'default'}
          onUpdate={update}
          nodes={nodes}
        />
      )}

      {type === 'action' && (
        <div className="space-y-3">
          <div>
            <Label>Tipo de accion</Label>
            <select
              className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                         text-sm text-[#e8e8f0] focus:outline-none focus:border-[#00f0ff]/50"
              value={data.actionType || ''}
              onChange={(e) => update('actionType', e.target.value)}
            >
              <option value="">Seleccionar...</option>
              <optgroup label="Tools nativos">
                {ACTION_TYPES.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </optgroup>
              {mcpTools.length > 0 && (
                <optgroup label="MCP Tools">
                  {mcpTools.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
              )}
              {apiTools.length > 0 && (
                <optgroup label="APIs">
                  {apiTools.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </optgroup>
              )}
            </select>
            {data.actionType?.startsWith('mcp:') && (
              <p className="text-[10px] text-[#00f0ff]/70 mt-1">
                Tool MCP — se ejecutara via servidor externo
              </p>
            )}
            {data.actionType?.startsWith('api:') && (
              <p className="text-[10px] text-[#00f0ff]/70 mt-1">
                API Integration — se ejecutara via HTTP directo
              </p>
            )}
          </div>
          <div>
            <Label>Variable de resultado</Label>
            <Input
              value={data.resultVariable}
              onChange={(v) => update('resultVariable', v)}
              placeholder="resultado"
            />
          </div>
          <ParametersEditor
            parameters={data.parameters || {}}
            onChange={(params) => update('parameters', params)}
          />
          <div>
            <Label>Mensaje si falla</Label>
            <TextArea
              value={data.onFailureMessage}
              onChange={(v) => update('onFailureMessage', v)}
              placeholder="Hubo un error..."
              rows={2}
            />
          </div>
        </div>
      )}

      {type === 'end' && (
        <div className="space-y-3">
          <div>
            <Label>Mensaje de despedida</Label>
            <TextArea
              value={data.message}
              onChange={(v) => update('message', v)}
              placeholder="Gracias por llamar..."
              rows={4}
            />
          </div>
          <Checkbox
            checked={data.hangup}
            onChange={(v) => update('hangup', v)}
            label="Colgar llamada al terminar"
          />
        </div>
      )}

      {type === 'transfer' && (
        <div className="space-y-3">
          <div>
            <Label>Mensaje antes de transferir</Label>
            <TextArea
              value={data.message}
              onChange={(v) => update('message', v)}
              placeholder="Te voy a transferir con un agente..."
              rows={3}
            />
          </div>
          <div>
            <Label>Numero de transferencia</Label>
            <Input
              value={data.transferNumber}
              onChange={(v) => update('transferNumber', v)}
              placeholder="+52..."
            />
            <p className="text-[10px] text-[#555570] mt-1">
              Numero SIP o telefono al que se transferira la llamada
            </p>
          </div>
        </div>
      )}

      {type === 'wait' && (
        <div className="space-y-3">
          <div>
            <Label>Segundos de espera</Label>
            <Input
              type="number"
              value={data.seconds}
              onChange={(v) => update('seconds', v)}
              placeholder="2"
            />
          </div>
          <div>
            <Label>Mensaje durante espera (opcional)</Label>
            <TextArea
              value={data.message}
              onChange={(v) => update('message', v)}
              placeholder="Un momento por favor..."
              rows={2}
            />
            <p className="text-[10px] text-[#555570] mt-1">
              Si se deja vacio, la pausa sera silenciosa
            </p>
          </div>
        </div>
      )}

      {type === 'loop' && (
        <LoopProperties data={data} onUpdate={update} nodes={nodes} />
      )}

      {type === 'collectMultiple' && (
        <CollectMultipleProperties data={data} onUpdate={update} />
      )}

      {/* Notas — disponible para TODOS los nodos */}
      <div className="mt-4 pt-4 border-t border-[#2a2a3e]">
        <Label>Notas</Label>
        <TextArea
          value={data.comment}
          onChange={(v) => update('comment', v)}
          placeholder="Notas internas sobre este nodo..."
          rows={2}
        />
        <p className="text-[10px] text-[#555570] mt-1">
          Visible como icono en el canvas. No afecta el flujo.
        </p>
      </div>

      <VariableInspector nodes={nodes} />
    </div>
  )
}

function ParametersEditor({ parameters, onChange }) {
  // Usar array interno con IDs estables para evitar bug de keys duplicadas
  const idRef = React.useRef(0)
  const [items, setItems] = React.useState(() =>
    Object.entries(parameters || {}).map(([k, v]) => ({ id: idRef.current++, key: k, value: v }))
  )

  // Sync: cuando el objeto externo cambia (undo/redo), reconstruir items
  const prevParamsRef = React.useRef(parameters)
  if (parameters !== prevParamsRef.current) {
    const extEntries = Object.entries(parameters || {})
    if (
      extEntries.length !== items.length ||
      extEntries.some(([k, v], i) => items[i]?.key !== k || items[i]?.value !== v)
    ) {
      // Reset items desde el objeto externo
      idRef.current = 0
      const newItems = extEntries.map(([k, v]) => ({ id: idRef.current++, key: k, value: v }))
      setItems(newItems)
    }
    prevParamsRef.current = parameters
  }

  const emitChange = (newItems) => {
    setItems(newItems)
    const obj = {}
    for (const item of newItems) {
      if (item.key || item.value) obj[item.key] = item.value
    }
    onChange(obj)
  }

  const addParam = () => {
    emitChange([...items, { id: idRef.current++, key: '', value: '' }])
  }

  const removeParam = (id) => {
    emitChange(items.filter(item => item.id !== id))
  }

  const updateItem = (id, field, val) => {
    emitChange(items.map(item => item.id === id ? { ...item, [field]: val } : item))
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Parametros</Label>
        <button
          onClick={addParam}
          className="text-xs text-[#00f0ff] hover:text-[#00f0ff]/80"
        >
          + Agregar
        </button>
      </div>
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-1">
          <input
            className="flex-1 bg-[#0a0a0f] border border-[#2a2a3e] rounded px-2 py-1
                       text-xs text-[#e8e8f0] placeholder-[#555570]
                       focus:outline-none focus:border-[#00f0ff]/50"
            value={item.key}
            onChange={(e) => updateItem(item.id, 'key', e.target.value)}
            placeholder="key"
          />
          <input
            className="flex-1 bg-[#0a0a0f] border border-[#2a2a3e] rounded px-2 py-1
                       text-xs text-[#e8e8f0] placeholder-[#555570]
                       focus:outline-none focus:border-[#00f0ff]/50"
            value={item.value}
            onChange={(e) => updateItem(item.id, 'value', e.target.value)}
            placeholder="{{variable}}"
          />
          <button
            onClick={() => removeParam(item.id)}
            className="text-red-400 hover:text-red-300 p-0.5"
            title="Eliminar"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
      {items.length === 0 && (
        <p className="text-[10px] text-[#555570] italic">
          {'Usa {{variable}} para insertar datos recopilados'}
        </p>
      )}
    </div>
  )
}

function VariableInspector({ nodes }) {
  const variables = React.useMemo(() => {
    const vars = []
    for (const node of nodes) {
      if (node.type === 'collectInput' && node.data.variableName) {
        const typeLabel = VARIABLE_TYPES.find(t => t.value === node.data.variableType)?.label || node.data.variableType
        vars.push({ name: node.data.variableName, type: typeLabel })
      }
      if (node.type === 'collectMultiple' && node.data.fields) {
        for (const f of node.data.fields) {
          if (f.name) {
            const typeLabel = VARIABLE_TYPES.find(t => t.value === f.type)?.label || f.type
            vars.push({ name: f.name, type: typeLabel })
          }
        }
      }
      if (node.type === 'start' && node.data.injectCallerInfo) {
        vars.push({ name: 'caller_number', type: 'Telefono' })
      }
      if (node.type === 'action' && node.data.resultVariable) {
        vars.push({ name: node.data.resultVariable, type: 'Resultado' })
      }
    }
    return vars
  }, [nodes])

  if (variables.length === 0) return null

  const copyVar = (name) => {
    navigator.clipboard.writeText(`{{${name}}}`)
  }

  return (
    <div className="mt-6 pt-4 border-t border-[#2a2a3e]">
      <h4 className="text-xs font-bold uppercase tracking-wider text-[#8888a0] mb-3">
        Variables del flujo
      </h4>
      <div className="space-y-1.5">
        {variables.map((v) => (
          <div key={v.name} className="flex items-center justify-between group">
            <span className="text-xs text-[#e8e8f0]">
              {v.name} <span className="text-[#555570]">({v.type})</span>
            </span>
            <button
              onClick={() => copyVar(v.name)}
              className="text-[10px] text-[#555570] hover:text-[#00f0ff] opacity-0 group-hover:opacity-100 transition-opacity"
              title={`Copiar {{${v.name}}}`}
            >
              copiar
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function ConditionProperties({ conditions, defaultHandleId, onUpdate, nodes = [] }) {
  const availableVars = React.useMemo(() => {
    const vars = []
    for (const node of nodes) {
      if (node.type === 'collectInput' && node.data.variableName) {
        vars.push(node.data.variableName)
      }
      if (node.type === 'start' && node.data.injectCallerInfo) {
        vars.push('caller_number')
      }
      if (node.type === 'action' && node.data.resultVariable) {
        vars.push(node.data.resultVariable)
      }
    }
    return vars
  }, [nodes])

  const addCondition = () => {
    const newCond = {
      variable: '',
      operator: 'equals',
      value: '',
      handleId: `cond-${Date.now()}`,
    }
    onUpdate('conditions', [...conditions, newCond])
  }

  const removeCondition = (index) => {
    onUpdate('conditions', conditions.filter((_, i) => i !== index))
  }

  const updateCondition = (index, key, value) => {
    const updated = conditions.map((c, i) => (i === index ? { ...c, [key]: value } : c))
    onUpdate('conditions', updated)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Condiciones</Label>
        <button
          onClick={addCondition}
          className="text-xs text-[#00f0ff] hover:text-[#00f0ff]/80"
        >
          + Agregar
        </button>
      </div>
      {conditions.map((cond, i) => (
        <div key={i} className="p-3 rounded-lg border border-[#2a2a3e] bg-[#0a0a0f] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#8888a0]">Condicion {i + 1}</span>
            <button
              onClick={() => removeCondition(i)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Eliminar
            </button>
          </div>
          {availableVars.length > 0 ? (
            <select
              className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                         text-sm text-[#e8e8f0] focus:outline-none focus:border-[#00f0ff]/50"
              value={cond.variable || ''}
              onChange={(e) => updateCondition(i, 'variable', e.target.value)}
            >
              <option value="">Seleccionar variable...</option>
              {availableVars.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          ) : (
            <Input
              value={cond.variable}
              onChange={(v) => updateCondition(i, 'variable', v)}
              placeholder="nombre de variable"
            />
          )}
          <Select
            value={cond.operator}
            onChange={(v) => updateCondition(i, 'operator', v)}
            options={OPERATORS}
          />
          {!['not_empty', 'empty'].includes(cond.operator) && (
            <Input
              value={cond.value}
              onChange={(v) => updateCondition(i, 'value', v)}
              placeholder="valor a comparar"
            />
          )}
        </div>
      ))}
      {conditions.length === 0 && (
        <p className="text-xs text-[#555570] italic">
          Agrega condiciones para ramificar el flujo
        </p>
      )}
    </div>
  )
}

function LoopProperties({ data, onUpdate, nodes = [] }) {
  const condition = data.condition || { variable: '', operator: 'equals', value: '' }

  const availableVars = React.useMemo(() => {
    const vars = []
    for (const node of nodes) {
      if (node.type === 'collectInput' && node.data.variableName) vars.push(node.data.variableName)
      if (node.type === 'collectMultiple' && node.data.fields) {
        for (const f of node.data.fields) {
          if (f.name) vars.push(f.name)
        }
      }
      if (node.type === 'start' && node.data.injectCallerInfo) vars.push('caller_number')
      if (node.type === 'action' && node.data.resultVariable) vars.push(node.data.resultVariable)
    }
    return vars
  }, [nodes])

  const updateCondField = (key, value) => {
    onUpdate('condition', { ...condition, [key]: value })
  }

  return (
    <div className="space-y-3">
      <div>
        <Label>Iteraciones maximas</Label>
        <Input
          type="number"
          value={data.maxIterations}
          onChange={(v) => onUpdate('maxIterations', Math.max(1, Math.min(20, v || 1)))}
          placeholder="5"
        />
      </div>
      <div>
        <Label>Variable de condicion</Label>
        {availableVars.length > 0 ? (
          <select
            className="w-full bg-[#0a0a0f] border border-[#2a2a3e] rounded-lg px-3 py-2
                       text-sm text-[#e8e8f0] focus:outline-none focus:border-[#00f0ff]/50"
            value={condition.variable || ''}
            onChange={(e) => updateCondField('variable', e.target.value)}
          >
            <option value="">Seleccionar variable...</option>
            {availableVars.map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        ) : (
          <Input
            value={condition.variable}
            onChange={(v) => updateCondField('variable', v)}
            placeholder="nombre de variable"
          />
        )}
      </div>
      <div>
        <Label>Operador</Label>
        <Select
          value={condition.operator}
          onChange={(v) => updateCondField('operator', v)}
          options={OPERATORS}
        />
      </div>
      {!['not_empty', 'empty'].includes(condition.operator) && (
        <div>
          <Label>Valor</Label>
          <Input
            value={condition.value}
            onChange={(v) => updateCondField('value', v)}
            placeholder="valor a comparar"
          />
        </div>
      )}
      <p className="text-[10px] text-[#555570] leading-relaxed">
        El bucle se repite hasta que la condicion sea verdadera o se alcance el maximo de iteraciones
      </p>
    </div>
  )
}

function CollectMultipleProperties({ data, onUpdate }) {
  const fields = data.fields || []

  const addField = () => {
    onUpdate('fields', [...fields, { name: '', type: 'text', prompt: '' }])
  }

  const removeField = (index) => {
    onUpdate('fields', fields.filter((_, i) => i !== index))
  }

  const updateField = (index, key, value) => {
    const updated = fields.map((f, i) => (i === index ? { ...f, [key]: value } : f))
    onUpdate('fields', updated)
  }

  const moveField = (index, direction) => {
    const newFields = [...fields]
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= newFields.length) return
    const temp = newFields[index]
    newFields[index] = newFields[targetIndex]
    newFields[targetIndex] = temp
    onUpdate('fields', newFields)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Campos a recopilar</Label>
        <button
          onClick={addField}
          className="text-xs text-[#00f0ff] hover:text-[#00f0ff]/80"
        >
          + Agregar campo
        </button>
      </div>
      {fields.map((field, i) => (
        <div key={i} className="p-3 rounded-lg border border-[#2a2a3e] bg-[#0a0a0f] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#8888a0]">Campo {i + 1}</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => moveField(i, -1)}
                disabled={i === 0}
                className="text-[10px] text-[#555570] hover:text-[#e8e8f0] disabled:opacity-30 px-1"
                title="Subir"
              >
                &#9650;
              </button>
              <button
                onClick={() => moveField(i, 1)}
                disabled={i === fields.length - 1}
                className="text-[10px] text-[#555570] hover:text-[#e8e8f0] disabled:opacity-30 px-1"
                title="Bajar"
              >
                &#9660;
              </button>
              <button
                onClick={() => removeField(i)}
                className="text-xs text-red-400 hover:text-red-300 ml-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#555570]">Nombre de variable</label>
            <Input
              value={field.name}
              onChange={(v) => updateField(i, 'name', v)}
              placeholder="nombre, telefono..."
            />
          </div>
          <div>
            <label className="text-[10px] text-[#555570]">Tipo</label>
            <Select
              value={field.type}
              onChange={(v) => updateField(i, 'type', v)}
              options={VARIABLE_TYPES}
            />
          </div>
          <div>
            <label className="text-[10px] text-[#555570]">Pregunta</label>
            <TextArea
              value={field.prompt}
              onChange={(v) => updateField(i, 'prompt', v)}
              placeholder="Como te llamas?"
              rows={2}
            />
          </div>
        </div>
      ))}
      {fields.length === 0 && (
        <p className="text-xs text-[#555570] italic">
          Agrega campos para recopilar multiples datos en secuencia
        </p>
      )}
      <div>
        <Label>Reintentos maximos por campo</Label>
        <Input
          type="number"
          value={data.maxRetries}
          onChange={(v) => onUpdate('maxRetries', v)}
          placeholder="3"
        />
      </div>
      <p className="text-[10px] text-[#555570] leading-relaxed">
        Recopila multiples datos en secuencia
      </p>
    </div>
  )
}
