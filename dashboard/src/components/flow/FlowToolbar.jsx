import React, { useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChatTesterButton } from '../ChatTester'

export function FlowToolbar({
  agentName,
  agentId,
  agentType,
  onSave,
  onValidate,
  onUndo,
  onRedo,
  onDuplicate,
  onCopy,
  onPaste,
  onExport,
  onImport,
  onOpenTemplates,
  onAutoLayout,
  onToggleMinimap,
  showMinimap,
  onToggleGrid,
  showGrid,
  onToggleValidation,
  showValidation,
  validationCount = 0,
  canUndo,
  canRedo,
  hasSelection,
  selectionCount = 0,
  saving,
  searchActive,
  searchQuery,
  onSearchChange,
  onSearchOpen,
  onSearchClose,
  searchResultCount = 0,
  searchCurrentIndex = 0,
  onSearchNext,
  onSearchPrev,
  flowData,
}) {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const searchInputRef = useRef(null)

  // Auto-focus search input cuando se abre
  useEffect(() => {
    if (searchActive && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [searchActive])

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      onImport(file)
      e.target.value = ''
    }
  }

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onSearchClose()
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) onSearchPrev()
      else onSearchNext()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      onSearchNext()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      onSearchPrev()
    }
  }

  return (
    <div className="h-14 bg-[#12121a] border-b border-[#2a2a3e] px-4 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
          title="Volver"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="w-px h-6 bg-[#2a2a3e]" />
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-[#e8e8f0]">
            {agentName || 'Flow Builder'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {/* Search bar */}
        {searchActive ? (
          <div className="flex items-center gap-1 mr-2">
            <div className="relative flex items-center">
              <svg className="w-3.5 h-3.5 absolute left-2.5 text-[#555570]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Buscar nodos..."
                className="w-48 pl-8 pr-2 py-1.5 text-xs rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]
                           text-[#e8e8f0] placeholder-[#555570] focus:border-[#00f0ff] focus:outline-none"
              />
            </div>
            {searchQuery.trim() && (
              <span className="text-[10px] text-[#8888a0] tabular-nums min-w-[50px] text-center">
                {searchResultCount > 0 ? `${searchCurrentIndex + 1}/${searchResultCount}` : 'Sin resultados'}
              </span>
            )}
            <button onClick={onSearchPrev} disabled={searchResultCount === 0}
              className="p-1 rounded text-[#8888a0] hover:text-[#e8e8f0] disabled:opacity-30" title="Anterior (Shift+Enter)">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            </button>
            <button onClick={onSearchNext} disabled={searchResultCount === 0}
              className="p-1 rounded text-[#8888a0] hover:text-[#e8e8f0] disabled:opacity-30" title="Siguiente (Enter)">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <button onClick={onSearchClose}
              className="p-1 rounded text-[#8888a0] hover:text-[#e8e8f0]" title="Cerrar (Esc)">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ) : (
          <button
            onClick={onSearchOpen}
            className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540] transition-colors"
            title="Buscar nodos (Ctrl+F)"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
        )}

        <div className="w-px h-6 bg-[#2a2a3e] mx-1" />

        {/* Undo/Redo */}
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
          title="Deshacer (Ctrl+Z)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" />
          </svg>
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
          title="Rehacer (Ctrl+Y)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10H11a5 5 0 00-5 5v2M21 10l-4-4M21 10l-4 4" />
          </svg>
        </button>

        <div className="w-px h-6 bg-[#2a2a3e] mx-1" />

        {/* Copy/Paste/Duplicate */}
        <button
          onClick={onCopy}
          disabled={!hasSelection}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
          title="Copiar (Ctrl+C)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </button>
        <button
          onClick={onPaste}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors"
          title="Pegar (Ctrl+V)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </button>
        <button
          onClick={onDuplicate}
          disabled={!hasSelection}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
          title="Duplicar nodo (Ctrl+D)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>

        <div className="w-px h-6 bg-[#2a2a3e] mx-1" />

        {/* Templates */}
        <button
          onClick={onOpenTemplates}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors"
          title="Plantillas"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
          </svg>
        </button>

        {/* Export */}
        <button
          onClick={onExport}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors"
          title="Exportar JSON"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>

        {/* Import */}
        <button
          onClick={handleImportClick}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors"
          title="Importar JSON"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="w-px h-6 bg-[#2a2a3e] mx-1" />

        {/* Auto-layout */}
        <button
          onClick={onAutoLayout}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors"
          title="Auto-layout (organizar nodos)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
          </svg>
        </button>

        {/* Grid toggle */}
        <button
          onClick={onToggleGrid}
          className={`p-2 rounded-lg transition-colors ${showGrid ? 'text-[#00f0ff] bg-[#00f0ff]/10' : 'text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]'}`}
          title={showGrid ? 'Ocultar grid' : 'Mostrar grid'}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h4v4H4V4zm6 0h4v4h-4V4zm6 0h4v4h-4V4zM4 10h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4zM4 16h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4z" />
          </svg>
        </button>

        {/* Minimap toggle */}
        <button
          onClick={onToggleMinimap}
          className={`p-2 rounded-lg transition-colors ${showMinimap ? 'text-[#00f0ff] bg-[#00f0ff]/10' : 'text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]'}`}
          title={showMinimap ? 'Ocultar minimapa' : 'Mostrar minimapa'}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </button>

        {/* Validation panel toggle */}
        <button
          onClick={onToggleValidation}
          className={`p-2 rounded-lg transition-colors relative ${showValidation ? 'text-[#00f0ff] bg-[#00f0ff]/10' : 'text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]'}`}
          title={showValidation ? 'Ocultar panel de validacion' : 'Mostrar panel de validacion'}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {validationCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-red-500 rounded-full
                             text-[8px] text-white font-bold flex items-center justify-center">
              {validationCount > 9 ? '9+' : validationCount}
            </span>
          )}
        </button>

        <div className="w-px h-6 bg-[#2a2a3e] mx-1" />

        {/* Validar, Probar y Guardar */}
        <button
          onClick={onValidate}
          className="px-4 py-1.5 text-sm rounded-lg border border-[#2a2a3e] text-[#8888a0]
                     hover:text-[#e8e8f0] hover:border-[#555570] transition-colors"
        >
          Validar
        </button>
        {agentId && (
          <ChatTesterButton
            agentId={agentId}
            agentName={agentName}
            agentType={agentType || 'inbound'}
            flowOverride={flowData}
            label="Probar flujo"
          />
        )}
        <button
          onClick={onSave}
          disabled={saving}
          className="px-4 py-1.5 text-sm rounded-lg bg-[#00f0ff] text-[#0a0a0f] font-medium
                     hover:bg-[#00f0ff]/90 transition-colors disabled:opacity-50"
        >
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
      </div>

      {/* Shortcuts hint + selection info */}
      <div className="hidden xl:flex items-center gap-3 text-[10px] text-[#555570]">
        {selectionCount > 1 && (
          <span className="text-[#00f0ff]">{selectionCount} seleccionados</span>
        )}
        <span>Del: borrar</span>
        <span>Ctrl+C/V: copiar/pegar</span>
        <span>Ctrl+F: buscar</span>
        <span>Ctrl+Z/Y: undo/redo</span>
        <span>Ctrl+S: guardar</span>
      </div>
    </div>
  )
}
