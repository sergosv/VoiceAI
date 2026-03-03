import React, { useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export function FlowToolbar({
  agentName,
  onSave,
  onValidate,
  onUndo,
  onRedo,
  onDuplicate,
  onExport,
  onImport,
  onOpenTemplates,
  canUndo,
  canRedo,
  hasSelection,
  saving,
  validating,
}) {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      onImport(file)
      e.target.value = '' // Reset para permitir re-importar mismo archivo
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

        {/* Duplicar */}
        <button
          onClick={onDuplicate}
          disabled={!hasSelection}
          className="p-2 rounded-lg text-[#8888a0] hover:text-[#e8e8f0] hover:bg-[#252540]
                     transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
          title="Duplicar nodo (Ctrl+D)"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
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

        {/* Validar y Guardar */}
        <button
          onClick={onValidate}
          disabled={validating}
          className="px-4 py-1.5 text-sm rounded-lg border border-[#2a2a3e] text-[#8888a0]
                     hover:text-[#e8e8f0] hover:border-[#555570] transition-colors
                     disabled:opacity-50"
        >
          {validating ? 'Validando...' : 'Validar'}
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="px-4 py-1.5 text-sm rounded-lg bg-[#00f0ff] text-[#0a0a0f] font-medium
                     hover:bg-[#00f0ff]/90 transition-colors disabled:opacity-50"
        >
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
      </div>

      {/* Shortcuts hint */}
      <div className="hidden xl:flex items-center gap-3 text-[10px] text-[#555570]">
        <span>Del: borrar</span>
        <span>Ctrl+D: duplicar</span>
        <span>Ctrl+Z/Y: undo/redo</span>
        <span>Ctrl+S: guardar</span>
      </div>
    </div>
  )
}
