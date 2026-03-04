import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Dagre from '@dagrejs/dagre'

import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { api } from '../lib/api'
import { nodeTypes } from '../components/flow/nodes'
import { NodePalette } from '../components/flow/NodePalette'
import { PropertiesPanel } from '../components/flow/PropertiesPanel'
import { FlowToolbar } from '../components/flow/FlowToolbar'
import { FlowTemplates } from '../components/flow/FlowTemplates'
import { ValidationPanel } from '../components/flow/ValidationPanel'

const DEFAULT_START_NODE = {
  id: 'start-1',
  type: 'start',
  position: { x: 300, y: 50 },
  data: { greeting: 'Hola, bienvenido. En que puedo ayudarte?' },
}

// Tamano maximo del historial de undo/redo
const MAX_HISTORY = 40

function FlowBuilderInner() {
  const { agentId } = useParams()
  const navigate = useNavigate()
  const { user, loading: authLoading } = useAuth()
  const toast = useToast()
  const reactFlowWrapper = useRef(null)
  const { screenToFlowPosition, setCenter } = useReactFlow()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState(null)
  const [agent, setAgent] = useState(null)
  const [clientId, setClientId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [mcpTools, setMcpTools] = useState([])
  const [apiTools, setApiTools] = useState([])
  const [validationErrors, setValidationErrors] = useState({}) // nodeId -> [errors]
  const [showTemplates, setShowTemplates] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [historyVersion, setHistoryVersion] = useState(0) // Trigger re-render on history change
  const [showMinimap, setShowMinimap] = useState(true)
  const [showValidationPanel, setShowValidationPanel] = useState(false)
  const [selectedNodeIds, setSelectedNodeIds] = useState([])
  const [showGrid, setShowGrid] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchActive, setSearchActive] = useState(false)
  const [searchCurrentIndex, setSearchCurrentIndex] = useState(0)

  // ── Clipboard para copy/paste ────────────────────────
  const clipboardRef = useRef({ nodes: [], edges: [] })

  // ── Undo/Redo ──────────────────────────────────────
  const historyRef = useRef({ past: [], future: [] })
  const skipHistoryRef = useRef(false)

  const pushHistory = useCallback((prevNodes, prevEdges) => {
    if (skipHistoryRef.current) return
    const h = historyRef.current
    h.past.push({ nodes: prevNodes, edges: prevEdges })
    if (h.past.length > MAX_HISTORY) h.past.shift()
    h.future = [] // Limpiar redo al hacer un cambio nuevo
    setHistoryVersion(v => v + 1)
    setIsDirty(true)
  }, [])

  const undo = useCallback(() => {
    const h = historyRef.current
    if (h.past.length === 0) return
    const prev = h.past.pop()
    h.future.push({ nodes, edges })
    skipHistoryRef.current = true
    setNodes(prev.nodes)
    setEdges(prev.edges)
    skipHistoryRef.current = false
    setSelectedNode(null)
    setHistoryVersion(v => v + 1)
  }, [nodes, edges, setNodes, setEdges])

  const redo = useCallback(() => {
    const h = historyRef.current
    if (h.future.length === 0) return
    const next = h.future.pop()
    h.past.push({ nodes, edges })
    skipHistoryRef.current = true
    setNodes(next.nodes)
    setEdges(next.edges)
    skipHistoryRef.current = false
    setSelectedNode(null)
    setHistoryVersion(v => v + 1)
  }, [nodes, edges, setNodes, setEdges])

  // ── Auto-layout con dagre ─────────────────────────
  const autoLayout = useCallback(() => {
    if (nodes.length === 0) return
    pushHistory(nodes, edges)

    const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}))
    g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 })

    for (const node of nodes) {
      g.setNode(node.id, { width: 200, height: 100 })
    }
    for (const edge of edges) {
      g.setEdge(edge.source, edge.target)
    }

    Dagre.layout(g)

    setNodes(nodes.map((node) => {
      const pos = g.node(node.id)
      return { ...node, position: { x: pos.x - 100, y: pos.y - 50 } }
    }))
    toast.info('Layout automático aplicado')
  }, [nodes, edges, setNodes, pushHistory, toast])

  // ── Copy / Paste ─────────────────────────────────────
  const copyNodes = useCallback(() => {
    const ids = selectedNodeIds.length > 0 ? selectedNodeIds : (selectedNode ? [selectedNode.id] : [])
    if (ids.length === 0) return

    // Filtrar nodos Start
    const copyable = nodes.filter(n => ids.includes(n.id) && n.type !== 'start')
    if (copyable.length === 0) {
      toast.info('No se puede copiar el nodo de inicio')
      return
    }

    const idSet = new Set(copyable.map(n => n.id))
    // Copiar edges internas entre los nodos seleccionados
    const internalEdges = edges.filter(e => idSet.has(e.source) && idSet.has(e.target))

    clipboardRef.current = { nodes: copyable, edges: internalEdges }
    // Guardar en localStorage para cross-flow paste
    try {
      localStorage.setItem('flow-clipboard', JSON.stringify({ nodes: copyable, edges: internalEdges }))
    } catch { /* ignorar */ }

    toast.info(`${copyable.length} nodo${copyable.length > 1 ? 's' : ''} copiado${copyable.length > 1 ? 's' : ''}`)
  }, [selectedNodeIds, selectedNode, nodes, edges, toast])

  const pasteNodes = useCallback(() => {
    let clipboard = clipboardRef.current
    // Intentar desde localStorage si el clipboard interno esta vacio
    if (clipboard.nodes.length === 0) {
      try {
        const stored = localStorage.getItem('flow-clipboard')
        if (stored) clipboard = JSON.parse(stored)
      } catch { /* ignorar */ }
    }
    if (!clipboard.nodes || clipboard.nodes.length === 0) return

    pushHistory(nodes, edges)

    const ts = Date.now()
    const idMap = {} // old id -> new id
    const newNodes = clipboard.nodes.map((n, i) => {
      const newId = `${n.type}-${ts}-${i}`
      idMap[n.id] = newId
      return {
        ...n,
        id: newId,
        position: { x: n.position.x + 50, y: n.position.y + 50 },
        data: { ...n.data },
        selected: false,
      }
    })

    const newEdges = clipboard.edges
      .filter(e => idMap[e.source] && idMap[e.target])
      .map((e, i) => ({
        ...e,
        id: `edge-paste-${ts}-${i}`,
        source: idMap[e.source],
        target: idMap[e.target],
      }))

    setNodes(nds => [...nds, ...newNodes])
    setEdges(eds => [...eds, ...newEdges])
    toast.info(`${newNodes.length} nodo${newNodes.length > 1 ? 's' : ''} pegado${newNodes.length > 1 ? 's' : ''}`)
  }, [nodes, edges, setNodes, setEdges, pushHistory, toast])

  // ── Search/Filter ───────────────────────────────────
  const searchResults = useMemo(() => {
    if (!searchActive || !searchQuery.trim()) return []
    const q = searchQuery.toLowerCase()
    return nodes.filter(n => {
      const d = n.data
      const texts = [
        d.label || '', d.message || '', d.greeting || '',
        d.prompt || '', d.variableName || '', d.actionType || '',
        d.onFailureMessage || '', d.retryMessage || '',
        d.transferNumber || '', n.type || '',
      ]
      return texts.some(t => t.toLowerCase().includes(q))
    })
  }, [searchActive, searchQuery, nodes])

  const searchResultIds = useMemo(() => new Set(searchResults.map(n => n.id)), [searchResults])

  const navigateSearch = useCallback((direction) => {
    if (searchResults.length === 0) return
    let nextIdx = searchCurrentIndex + direction
    if (nextIdx < 0) nextIdx = searchResults.length - 1
    if (nextIdx >= searchResults.length) nextIdx = 0
    setSearchCurrentIndex(nextIdx)
    const node = searchResults[nextIdx]
    if (node) {
      setCenter(node.position.x + 100, node.position.y + 50, { zoom: 1.2, duration: 400 })
    }
  }, [searchResults, searchCurrentIndex, setCenter])

  const closeSearch = useCallback(() => {
    setSearchActive(false)
    setSearchQuery('')
    setSearchCurrentIndex(0)
  }, [])

  // Wrapper para onNodesChange que guarda historial
  const handleNodesChange = useCallback((changes) => {
    // Solo guardar historial para cambios significativos (no drag en progreso)
    const significant = changes.some(c =>
      c.type === 'remove' || c.type === 'add' ||
      (c.type === 'position' && !c.dragging)
    )
    if (significant) pushHistory(nodes, edges)
    onNodesChange(changes)
  }, [onNodesChange, pushHistory, nodes, edges])

  const handleEdgesChange = useCallback((changes) => {
    const significant = changes.some(c => c.type === 'remove' || c.type === 'add')
    if (significant) pushHistory(nodes, edges)
    onEdgesChange(changes)
  }, [onEdgesChange, pushHistory, nodes, edges])

  // ── Beforeunload guard ───────────────────────────────
  useEffect(() => {
    if (!isDirty) return
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // ── Auth ───────────────────────────────────────────
  useEffect(() => {
    if (!authLoading && !user) navigate('/login')
  }, [user, authLoading, navigate])

  useEffect(() => {
    if (!authLoading && user) loadAgent()
  }, [agentId, authLoading, user])

  async function loadAgent() {
    setLoading(true)
    try {
      const cid = user?.client_id
      let agentData
      if (user?.role === 'admin') {
        const clients = await api.get('/clients')
        for (const c of clients) {
          try {
            agentData = await api.get(`/clients/${c.id}/agents/${agentId}`)
            break
          } catch { /* continuar */ }
        }
        if (!agentData) throw new Error('Agente no encontrado')
      } else {
        agentData = await api.get(`/clients/${cid}/agents/${agentId}`)
      }

      setAgent(agentData)
      setClientId(agentData.client_id)

      // Cargar MCP tools disponibles
      try {
        const servers = await api.get(`/clients/${agentData.client_id}/mcp-servers`)
        const tools = []
        for (const srv of servers) {
          if (!srv.is_active) continue
          if (srv.agent_ids && !srv.agent_ids.includes(agentId)) continue
          for (const t of (srv.tools_cache || [])) {
            tools.push({
              value: `mcp:${srv.name}:${t.name}`,
              label: `${t.name} (${srv.name})`,
              description: t.description || '',
              serverName: srv.name,
            })
          }
        }
        setMcpTools(tools)
      } catch { /* sin MCP */ }

      // Cargar API integrations disponibles
      try {
        const integrations = await api.get(`/clients/${agentData.client_id}/api-integrations`)
        const aTools = []
        for (const integ of integrations) {
          if (!integ.is_active) continue
          if (integ.agent_ids && !integ.agent_ids.includes(agentId)) continue
          aTools.push({
            value: `api:${integ.name}`,
            label: `${integ.name}`,
            description: integ.description || '',
          })
        }
        setApiTools(aTools)
      } catch { /* sin API integrations */ }

      // Cargar flujo existente o mostrar templates
      const flow = agentData.conversation_flow
      if (flow && flow.nodes && flow.nodes.length > 0) {
        setNodes(flow.nodes)
        setEdges(flow.edges || [])
      } else {
        setNodes([DEFAULT_START_NODE])
        setEdges([])
        setShowTemplates(true)
      }
    } catch (err) {
      toast.error('Error cargando agente: ' + err.message)
      navigate(-1)
    } finally {
      setLoading(false)
    }
  }

  // ── Connection validation ─────────────────────────
  const isValidConnection = useCallback((connection) => {
    const { source, target } = connection

    // No self-loops
    if (source === target) return false

    // No conectar AL nodo Start (solo puede ser source)
    const targetNode = nodes.find(n => n.id === target)
    if (targetNode?.type === 'start') return false

    // No conectar DESDE un nodo End o Transfer (solo pueden ser target)
    const sourceNode = nodes.find(n => n.id === source)
    if (sourceNode?.type === 'end' || sourceNode?.type === 'transfer') return false

    // No duplicar conexiones exactas
    const exists = edges.some(
      e => e.source === source && e.target === target &&
        (e.sourceHandle || 'default') === (connection.sourceHandle || 'default')
    )
    if (exists) return false

    return true
  }, [nodes, edges])

  // ── Conectar con labels automaticos ────────────────
  const onConnect = useCallback(
    (params) => {
      pushHistory(nodes, edges)
      const sourceNode = nodes.find(n => n.id === params.source)
      let label = ''

      // Auto-label para condiciones
      if (sourceNode?.type === 'condition') {
        const conditions = sourceNode.data.conditions || []
        const defaultHandle = sourceNode.data.defaultHandleId || 'default'
        if (params.sourceHandle === defaultHandle) {
          label = 'default'
        } else {
          const cond = conditions.find(c => c.handleId === params.sourceHandle)
          if (cond) {
            label = `${cond.variable} ${cond.operator} ${cond.value || '""'}`
          }
        }
      }

      // Auto-label para yes/no y maxRetries de collectInput
      if (sourceNode?.type === 'collectInput') {
        if (params.sourceHandle === 'yes') label = 'Si'
        else if (params.sourceHandle === 'no') label = 'No'
        else if (params.sourceHandle === 'maxRetries') label = 'Max reintentos'
      }

      // Auto-label para action success/failure
      if (sourceNode?.type === 'action') {
        if (params.sourceHandle === 'success') label = 'OK'
        else if (params.sourceHandle === 'failure') label = 'Error'
      }

      setEdges((eds) => addEdge({
        ...params,
        animated: true,
        label: label || undefined,
        labelStyle: label ? { fill: '#8888a0', fontSize: 11 } : undefined,
        labelBgStyle: label ? { fill: '#12121a', fillOpacity: 0.9 } : undefined,
        labelBgPadding: label ? [6, 3] : undefined,
        labelBgBorderRadius: 4,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#555570', width: 16, height: 16 },
        style: { stroke: '#555570' },
      }, eds))
    },
    [setEdges, nodes, pushHistory, edges],
  )

  // ── Seleccion ──────────────────────────────────────
  const onSelectionChange = useCallback(({ nodes: selectedNodes }) => {
    setSelectedNode(selectedNodes.length === 1 ? selectedNodes[0] : null)
    setSelectedNodeIds(selectedNodes.map(n => n.id))
  }, [])

  const onEdgeClick = useCallback((_, edge) => {
    setSelectedEdgeId(edge.id)
    setSelectedNode(null)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedEdgeId(null)
  }, [])

  // ── Actualizar data de nodo ────────────────────────
  const onNodeDataChange = useCallback((nodeId, key, value) => {
    pushHistory(nodes, edges)

    // Limpiar edges huerfanos al cambiar condiciones
    if (key === 'conditions') {
      const node = nodes.find(n => n.id === nodeId)
      if (node && node.type === 'condition') {
        const oldHandleIds = new Set((node.data.conditions || []).map(c => c.handleId))
        const newHandleIds = new Set((value || []).map(c => c.handleId))
        const removedHandles = [...oldHandleIds].filter(h => !newHandleIds.has(h))
        if (removedHandles.length > 0) {
          setEdges((eds) => eds.filter(
            e => !(e.source === nodeId && removedHandles.includes(e.sourceHandle))
          ))
        }
      }
    }

    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const updated = { ...node, data: { ...node.data, [key]: value } }
          setSelectedNode(updated)
          return updated
        }
        return node
      }),
    )
  }, [setNodes, setEdges, pushHistory, nodes, edges])

  // ── Drop desde paleta ──────────────────────────────
  const onDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      const type = e.dataTransfer.getData('application/reactflow')
      if (!type) return

      const position = screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      })

      pushHistory(nodes, edges)

      const newNode = {
        id: `${type}-${Date.now()}`,
        type,
        position,
        data: getDefaultData(type),
      }

      setNodes((nds) => [...nds, newNode])
    },
    [screenToFlowPosition, setNodes, pushHistory, nodes, edges],
  )

  // ── Duplicar nodo ──────────────────────────────────
  const duplicateNode = useCallback(() => {
    if (!selectedNode) return
    if (selectedNode.type === 'start') {
      toast.info('No se puede duplicar el nodo de inicio')
      return
    }
    pushHistory(nodes, edges)
    const newNode = {
      ...selectedNode,
      id: `${selectedNode.type}-${Date.now()}`,
      position: {
        x: selectedNode.position.x + 40,
        y: selectedNode.position.y + 60,
      },
      data: { ...selectedNode.data },
      selected: false,
    }
    setNodes((nds) => [...nds, newNode])
    toast.info('Nodo duplicado')
  }, [selectedNode, setNodes, pushHistory, nodes, edges, toast])

  // ── Templates ────────────────────────────────────────
  const handleSelectTemplate = useCallback((templateNodes, templateEdges) => {
    pushHistory(nodes, edges)
    setNodes(templateNodes)
    setEdges(templateEdges)
    toast.success('Plantilla aplicada')
  }, [setNodes, setEdges, pushHistory, nodes, edges, toast])

  // ── Export / Import ─────────────────────────────────
  const handleExport = useCallback(() => {
    const data = JSON.stringify({ nodes, edges }, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `flow-${agent?.name || agentId}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.info('Flujo exportado')
  }, [nodes, edges, agent, agentId, toast])

  const handleImport = useCallback((file) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target.result)
        if (!parsed.nodes || !Array.isArray(parsed.nodes)) {
          toast.error('Archivo invalido: falta propiedad "nodes"')
          return
        }
        pushHistory(nodes, edges)
        setNodes(parsed.nodes)
        setEdges(parsed.edges || [])
        toast.success(`Flujo importado (${parsed.nodes.length} nodos)`)
      } catch {
        toast.error('Error leyendo el archivo JSON')
      }
    }
    reader.readAsText(file)
  }, [setNodes, setEdges, pushHistory, nodes, edges, toast])

  // ── Guardar ────────────────────────────────────────
  const handleSave = async () => {
    if (!clientId) return
    setSaving(true)
    try {
      const flowData = { nodes, edges }
      await api.patch(`/clients/${clientId}/agents/${agentId}`, {
        conversation_flow: flowData,
        conversation_mode: 'flow',
      })
      setValidationErrors({})
      setIsDirty(false)
      toast.success('Flujo guardado correctamente')
    } catch (err) {
      toast.error('Error guardando: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // ── Validar (local, sin guardar) ────────────────────
  const handleValidate = () => {
    const nodeErrors = buildNodeErrors(nodes, edges)
    const errorCount = Object.values(nodeErrors).reduce((sum, arr) => sum + arr.length, 0)

    if (errorCount === 0) {
      setValidationErrors({})
      setShowValidationPanel(false)
      toast.success(`Flujo valido (${nodes.length} nodos, ${edges.length} conexiones)`)
    } else {
      setValidationErrors(nodeErrors)
      setShowValidationPanel(true)
      const msgs = Object.entries(nodeErrors).flatMap(([, errs]) => errs)
      toast.error(`${errorCount} problema${errorCount > 1 ? 's' : ''}: ${msgs.slice(0, 3).join(', ')}`)
    }
  }

  // ── Keyboard shortcuts ─────────────────────────────
  const onKeyDown = useCallback((e) => {
    // Escape cierra la busqueda
    if (e.key === 'Escape' && searchActive) {
      e.preventDefault()
      closeSearch()
      return
    }

    // Ctrl+F = Buscar
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault()
      setSearchActive(true)
      return
    }

    // Ignorar si esta escribiendo en un input/textarea
    const tag = e.target.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

    // Ctrl+Z / Cmd+Z = Undo
    if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
      e.preventDefault()
      undo()
      return
    }
    // Ctrl+Y / Cmd+Shift+Z = Redo
    if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault()
      redo()
      return
    }
    // Ctrl+C = Copiar
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
      e.preventDefault()
      copyNodes()
      return
    }
    // Ctrl+V = Pegar
    if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
      e.preventDefault()
      pasteNodes()
      return
    }
    // Ctrl+D = Duplicar
    if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
      e.preventDefault()
      duplicateNode()
      return
    }
    // Ctrl+S = Guardar
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      handleSave()
      return
    }

    // Delete/Backspace
    if (e.key === 'Delete' || e.key === 'Backspace') {
      // Borrar edge seleccionado
      if (selectedEdgeId) {
        pushHistory(nodes, edges)
        setEdges((eds) => eds.filter((edge) => edge.id !== selectedEdgeId))
        setSelectedEdgeId(null)
        return
      }
      // Multi-select bulk delete
      if (selectedNodeIds.length > 1) {
        const deletableIds = selectedNodeIds.filter(id => {
          const n = nodes.find(nd => nd.id === id)
          return n && n.type !== 'start'
        })
        if (deletableIds.length === 0) {
          toast.info('No se puede eliminar el nodo de inicio')
          return
        }
        pushHistory(nodes, edges)
        const idsSet = new Set(deletableIds)
        setNodes((nds) => nds.filter((n) => !idsSet.has(n.id)))
        setEdges((eds) => eds.filter((edge) => !idsSet.has(edge.source) && !idsSet.has(edge.target)))
        setSelectedNode(null)
        setSelectedNodeIds([])
        toast.info(`${deletableIds.length} nodo${deletableIds.length > 1 ? 's' : ''} eliminado${deletableIds.length > 1 ? 's' : ''}`)
        return
      }
      // Borrar nodo seleccionado
      if (selectedNode) {
        if (selectedNode.type === 'start') {
          toast.info('No se puede eliminar el nodo de inicio')
          return
        }
        pushHistory(nodes, edges)
        setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
        setEdges((eds) => eds.filter((edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id))
        setSelectedNode(null)
      }
    }
  }, [selectedNode, selectedNodeIds, selectedEdgeId, setNodes, setEdges, toast, undo, redo, duplicateNode, copyNodes, pasteNodes, handleSave, pushHistory, nodes, edges, searchActive, closeSearch])

  // ── Edges con highlight de seleccion ───────────────
  const styledEdges = useMemo(() =>
    edges.map(e => ({
      ...e,
      style: {
        ...e.style,
        stroke: e.id === selectedEdgeId ? '#00f0ff' : (e.style?.stroke || '#555570'),
        strokeWidth: e.id === selectedEdgeId ? 3 : 2,
      },
    }))
  , [edges, selectedEdgeId])

  // ── Nodos con errores de validacion + search dimming ─
  const styledNodes = useMemo(() => {
    const isSearching = searchActive && searchQuery.trim()
    return nodes.map((n, idx) => {
      let className = ''
      if (isSearching) {
        if (searchResultIds.has(n.id)) {
          // Encontrar indice en searchResults para resaltar current
          const matchIdx = searchResults.findIndex(r => r.id === n.id)
          className = matchIdx === searchCurrentIndex ? 'search-current' : 'search-match'
        } else {
          className = 'dimmed'
        }
      }
      return {
        ...n,
        className,
        data: {
          ...n.data,
          _validationErrors: validationErrors[n.id] || [],
        },
      }
    })
  }, [nodes, validationErrors, searchActive, searchQuery, searchResultIds, searchResults, searchCurrentIndex])

  if (loading || authLoading) {
    return (
      <div className="h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#00f0ff] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f]" onKeyDown={onKeyDown} tabIndex={0}>
      <FlowToolbar
        agentName={agent?.name}
        agentId={agentId}
        agentType={agent?.agent_type || 'inbound'}
        onSave={handleSave}
        onValidate={handleValidate}
        onUndo={undo}
        onRedo={redo}
        onDuplicate={duplicateNode}
        onCopy={copyNodes}
        onPaste={pasteNodes}
        onExport={handleExport}
        onImport={handleImport}
        onOpenTemplates={() => setShowTemplates(true)}
        onAutoLayout={autoLayout}
        onToggleMinimap={() => setShowMinimap(m => !m)}
        showMinimap={showMinimap}
        onToggleGrid={() => setShowGrid(g => !g)}
        showGrid={showGrid}
        onToggleValidation={() => setShowValidationPanel(v => !v)}
        showValidation={showValidationPanel}
        validationCount={Object.values(validationErrors).reduce((s, a) => s + a.length, 0)}
        canUndo={historyRef.current.past.length > 0}
        canRedo={historyRef.current.future.length > 0}
        hasSelection={!!selectedNode}
        selectionCount={selectedNodeIds.length}
        saving={saving}
        searchActive={searchActive}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchOpen={() => setSearchActive(true)}
        onSearchClose={closeSearch}
        searchResultCount={searchResults.length}
        searchCurrentIndex={searchCurrentIndex}
        onSearchNext={() => navigateSearch(1)}
        onSearchPrev={() => navigateSearch(-1)}
      />
      <FlowTemplates
        open={showTemplates}
        onClose={() => setShowTemplates(false)}
        onSelect={handleSelectTemplate}
      />
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />
        <div className="flex-1" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={styledNodes}
            edges={styledEdges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            isValidConnection={isValidConnection}
            selectionOnDrag
            selectionMode="partial"
            fitView
            snapToGrid
            snapGrid={[16, 16]}
            deleteKeyCode={null}
            defaultEdgeOptions={{
              animated: true,
              markerEnd: { type: MarkerType.ArrowClosed, color: '#555570', width: 16, height: 16 },
              style: { stroke: '#555570' },
            }}
          >
            <Controls position="bottom-left" />
            {showGrid && (
              <Background
                variant={BackgroundVariant.Dots}
                color="#2a2a3e"
                gap={16}
                size={1.5}
              />
            )}
            {showMinimap && (
              <MiniMap
                nodeColor={(n) => {
                  const colors = {
                    start: '#22c55e',
                    message: '#60a5fa',
                    collectInput: '#fbbf24',
                    condition: '#a78bfa',
                    action: '#00f0ff',
                    end: '#f87171',
                    transfer: '#fb923c',
                    wait: '#9ca3af',
                  }
                  return colors[n.type] || '#555570'
                }}
                maskColor="rgba(10, 10, 15, 0.7)"
                position="bottom-right"
              />
            )}
          </ReactFlow>
          {showValidationPanel && (
            <ValidationPanel
              errors={validationErrors}
              nodes={nodes}
              onClose={() => setShowValidationPanel(false)}
              onNavigateToNode={(nodeId) => {
                const node = nodes.find(n => n.id === nodeId)
                if (node) {
                  setCenter(node.position.x + 100, node.position.y + 50, { zoom: 1.2, duration: 500 })
                  setSelectedNode(node)
                }
              }}
            />
          )}
        </div>
        <PropertiesPanel
          selectedNode={selectedNode}
          onNodeDataChange={onNodeDataChange}
          mcpTools={mcpTools}
          apiTools={apiTools}
          nodes={nodes}
        />
      </div>
    </div>
  )
}

// Wrapper con ReactFlowProvider
export function FlowBuilder() {
  return (
    <ReactFlowProvider>
      <FlowBuilderInner />
    </ReactFlowProvider>
  )
}

function getDefaultData(type) {
  switch (type) {
    case 'message':
      return { message: '', waitForResponse: true }
    case 'collectInput':
      return {
        variableName: '',
        variableType: 'text',
        prompt: '',
        retryMessage: 'No entendi, puedes repetirlo?',
        maxRetries: 3,
      }
    case 'condition':
      return { conditions: [], defaultHandleId: 'default' }
    case 'action':
      return {
        actionType: '',
        parameters: {},
        resultVariable: '',
        onFailureMessage: 'Hubo un error, disculpa.',
      }
    case 'end':
      return { message: 'Gracias por llamar. Hasta luego.', hangup: false }
    case 'transfer':
      return { message: 'Te voy a transferir con un agente.', transferNumber: '' }
    case 'wait':
      return { seconds: 2, message: '' }
    default:
      return {}
  }
}

/** Genera errores de validacion por nodo ID. */
function buildNodeErrors(nodes, edges) {
  const errors = {}
  const addError = (nodeId, msg) => {
    if (!errors[nodeId]) errors[nodeId] = []
    errors[nodeId].push(msg)
  }

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))
  const sourceIds = new Set(edges.map(e => e.source))
  const targetIds = new Set(edges.map(e => e.target))

  // Recopilar variables definidas en el flujo
  const definedVars = new Set()
  for (const node of nodes) {
    if (node.type === 'collectInput' && node.data.variableName) {
      definedVars.add(node.data.variableName)
    }
    if (node.type === 'start' && node.data.injectCallerInfo) {
      definedVars.add('caller_number')
    }
    // action resultVariable tambien define una variable
    if (node.type === 'action' && node.data.resultVariable) {
      definedVars.add(node.data.resultVariable)
    }
  }

  for (const node of nodes) {
    const { id, type, data } = node

    // Start sin salida
    if (type === 'start' && !sourceIds.has(id)) {
      addError(id, 'Sin conexion de salida')
    }

    // Nodos intermedios sin entrada (excepto start)
    if (type !== 'start' && !targetIds.has(id)) {
      addError(id, 'Nodo desconectado — sin entrada')
    }

    // Nodos intermedios sin salida (excepto end y transfer — son terminales)
    if (!['end', 'start', 'transfer'].includes(type) && !sourceIds.has(id)) {
      addError(id, 'Sin conexion de salida')
    }

    // CollectInput sin variable
    if (type === 'collectInput' && !data.variableName) {
      addError(id, 'Falta nombre de variable')
    }

    // CollectInput sin prompt
    if (type === 'collectInput' && !data.prompt?.trim()) {
      addError(id, 'Falta pregunta al usuario')
    }

    // Message vacio
    if (type === 'message' && !data.message?.trim()) {
      addError(id, 'Mensaje vacio')
    }

    // End vacio
    if (type === 'end' && !data.message?.trim()) {
      addError(id, 'Mensaje de despedida vacio')
    }

    // Action sin tipo
    if (type === 'action' && !data.actionType) {
      addError(id, 'Falta tipo de accion')
    }

    // Action sin ruta de failure
    if (type === 'action' && data.actionType) {
      const hasFailureEdge = edges.some(
        e => e.source === id && e.sourceHandle === 'failure'
      )
      if (!hasFailureEdge) {
        addError(id, 'Sin ruta de error (failure)')
      }
    }

    // Condition sin condiciones
    if (type === 'condition' && (!data.conditions || data.conditions.length === 0)) {
      addError(id, 'Sin condiciones definidas')
    }

    // Condition con variable no definida
    if (type === 'condition' && data.conditions) {
      for (const cond of data.conditions) {
        if (cond.variable && !definedVars.has(cond.variable)) {
          addError(id, `Variable "${cond.variable}" no esta definida en ningun nodo`)
        }
      }
    }

    // Transfer sin numero
    if (type === 'transfer' && !data.transferNumber) {
      addError(id, 'Falta numero de transferencia')
    }

    // Variables huerfanas: escanear {{var}} en mensajes/prompts
    const textsToScan = []
    if (type === 'message') textsToScan.push(data.message || '')
    if (type === 'end') textsToScan.push(data.message || '')
    if (type === 'collectInput') textsToScan.push(data.prompt || '', data.retryMessage || '')
    if (type === 'start') textsToScan.push(data.greeting || '')
    if (type === 'action') textsToScan.push(data.onFailureMessage || '')
    if (type === 'transfer') textsToScan.push(data.message || '')
    if (type === 'wait') textsToScan.push(data.message || '')

    const varPattern = /\{\{(\w+)\}\}/g
    const usedVarsInNode = new Set()
    for (const txt of textsToScan) {
      let match
      while ((match = varPattern.exec(txt)) !== null) {
        usedVarsInNode.add(match[1])
      }
    }
    for (const v of usedVarsInNode) {
      if (!definedVars.has(v)) {
        addError(id, `Variable "{{${v}}}" no esta definida en el flujo`)
      }
    }
  }

  // Detectar ciclos con DFS
  const adjacency = {}
  for (const e of edges) {
    if (!adjacency[e.source]) adjacency[e.source] = []
    adjacency[e.source].push(e.target)
  }

  const visited = new Set()
  const recStack = new Set()
  const cycleNodes = new Set()

  function dfsCycle(nid, path) {
    visited.add(nid)
    recStack.add(nid)
    for (const neighbor of (adjacency[nid] || [])) {
      if (!visited.has(neighbor)) {
        dfsCycle(neighbor, [...path, neighbor])
      } else if (recStack.has(neighbor)) {
        const cycleStart = path.indexOf(neighbor)
        if (cycleStart >= 0) {
          const cyclePath = path.slice(cycleStart)
          cyclePath.push(neighbor)
          cyclePath.forEach(n => cycleNodes.add(n))
        } else {
          cycleNodes.add(neighbor)
          cycleNodes.add(nid)
        }
      }
    }
    recStack.delete(nid)
  }

  for (const node of nodes) {
    if (!visited.has(node.id)) {
      dfsCycle(node.id, [node.id])
    }
  }

  for (const nid of cycleNodes) {
    addError(nid, '(aviso) Parte de un ciclo — verificar que sea intencional')
  }

  return errors
}
