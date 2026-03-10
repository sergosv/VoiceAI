import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../lib/api'

function timeAgo(dateStr) {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHr / 24)

  if (diffSec < 60) return 'hace unos segundos'
  if (diffMin < 60) return `hace ${diffMin} min`
  if (diffHr < 24) return `hace ${diffHr} hora${diffHr > 1 ? 's' : ''}`
  if (diffDays < 30) return `hace ${diffDays} dia${diffDays > 1 ? 's' : ''}`
  return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function FlowVersions({ open, onClose, clientId, agentId, currentFlow, onLoadVersion, onRestore, toast }) {
  const [versions, setVersions] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(null) // version id being published
  const [deleting, setDeleting] = useState(null) // version id being deleted
  const [newLabel, setNewLabel] = useState('')
  const [showSaveForm, setShowSaveForm] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)

  const basePath = `/clients/${clientId}/agents/${agentId}/flow-versions`

  const loadVersions = useCallback(async () => {
    if (!clientId || !agentId) return
    setLoading(true)
    try {
      const data = await api.get(basePath)
      setVersions(data || [])
    } catch (err) {
      toast?.error?.('Error cargando versiones: ' + err.message)
    } finally {
      setLoading(false)
    }
  }, [clientId, agentId, basePath, toast])

  useEffect(() => {
    if (open) {
      loadVersions()
      setShowSaveForm(false)
      setConfirmDelete(null)
    }
  }, [open, loadVersions])

  const handleSaveVersion = async () => {
    if (!currentFlow) return
    setSaving(true)
    try {
      await api.post(basePath, {
        flow_data: currentFlow,
        label: newLabel.trim() || undefined,
      })
      setNewLabel('')
      setShowSaveForm(false)
      toast?.success?.('Version guardada')
      await loadVersions()
    } catch (err) {
      toast?.error?.('Error guardando version: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async (versionId) => {
    setPublishing(versionId)
    try {
      await api.post(`${basePath}/${versionId}/publish`)
      toast?.success?.('Version publicada')
      await loadVersions()
    } catch (err) {
      toast?.error?.('Error publicando version: ' + err.message)
    } finally {
      setPublishing(null)
    }
  }

  const handleDelete = async (versionId) => {
    setDeleting(versionId)
    try {
      await api.delete(`${basePath}/${versionId}`)
      toast?.success?.('Version eliminada')
      setConfirmDelete(null)
      await loadVersions()
    } catch (err) {
      toast?.error?.('Error eliminando version: ' + err.message)
    } finally {
      setDeleting(null)
    }
  }

  const handleView = async (versionId) => {
    try {
      const data = await api.get(`${basePath}/${versionId}`)
      if (data?.flow_data && onLoadVersion) {
        onLoadVersion(data.flow_data, data.version, versionId)
        onClose()
      }
    } catch (err) {
      toast?.error?.('Error cargando version: ' + err.message)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-[#12121a] border border-[#2a2a3e] rounded-xl shadow-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a3e] shrink-0">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-[#00f0ff]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-base font-semibold text-[#e8e8f0]">Versiones del flujo</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Save new version */}
        <div className="px-5 py-3 border-b border-[#2a2a3e] shrink-0">
          {showSaveForm ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newLabel}
                onChange={e => setNewLabel(e.target.value)}
                placeholder="Etiqueta (opcional, ej: 'Antes de cambiar saludo')"
                className="flex-1 px-3 py-1.5 text-sm rounded-lg bg-[#1a1a2e] border border-[#2a2a3e]
                           text-[#e8e8f0] placeholder-[#555570] focus:border-[#00f0ff] focus:outline-none"
                autoFocus
                onKeyDown={e => e.key === 'Enter' && handleSaveVersion()}
              />
              <button
                onClick={handleSaveVersion}
                disabled={saving}
                className="px-3 py-1.5 text-sm rounded-lg bg-[#00f0ff] text-[#0a0a0f] font-medium
                           hover:bg-[#00f0ff]/90 transition-colors disabled:opacity-50 whitespace-nowrap"
              >
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
              <button
                onClick={() => setShowSaveForm(false)}
                className="p-1.5 rounded text-[#8888a0] hover:text-[#e8e8f0] transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowSaveForm(true)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-dashed border-[#2a2a3e]
                         text-[#8888a0] hover:text-[#00f0ff] hover:border-[#00f0ff]/40 transition-colors
                         flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Guardar version actual
            </button>
          )}
        </div>

        {/* Version list */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-[#00f0ff] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : versions.length === 0 ? (
            <div className="text-center py-8">
              <svg className="w-10 h-10 mx-auto mb-3 text-[#2a2a3e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-[#555570]">Sin versiones guardadas</p>
              <p className="text-xs text-[#3a3a50] mt-1">Guarda una version para poder restaurarla despues</p>
            </div>
          ) : (
            <div className="space-y-2">
              {versions.map((v) => (
                <div
                  key={v.id}
                  className="p-3 rounded-lg border border-[#2a2a3e] bg-[#0e0e18] hover:border-[#3a3a50] transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[#e8e8f0]">
                        v{v.version}
                      </span>
                      {v.is_published && (
                        <span className="px-1.5 py-0.5 text-[10px] rounded bg-green-500/15 text-green-400 border border-green-500/30 font-medium">
                          Publicada
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-[#555570]">{timeAgo(v.created_at)}</span>
                  </div>

                  {v.label && (
                    <p className="text-xs text-[#8888a0] mb-2">{v.label}</p>
                  )}

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleView(v.id)}
                      className="px-2.5 py-1 text-[11px] rounded bg-[#1a1a2e] text-[#8888a0]
                                 hover:text-[#e8e8f0] hover:bg-[#252540] transition-colors border border-[#2a2a3e]"
                    >
                      Ver
                    </button>
                    {!v.is_published && (
                      <button
                        onClick={() => handlePublish(v.id)}
                        disabled={publishing === v.id}
                        className="px-2.5 py-1 text-[11px] rounded bg-[#00f0ff]/10 text-[#00f0ff]
                                   hover:bg-[#00f0ff]/20 transition-colors border border-[#00f0ff]/30
                                   disabled:opacity-50"
                      >
                        {publishing === v.id ? 'Publicando...' : 'Publicar'}
                      </button>
                    )}
                    {!v.is_published && (
                      <>
                        {confirmDelete === v.id ? (
                          <div className="flex items-center gap-1 ml-auto">
                            <span className="text-[10px] text-red-400">Seguro?</span>
                            <button
                              onClick={() => handleDelete(v.id)}
                              disabled={deleting === v.id}
                              className="px-2 py-1 text-[10px] rounded bg-red-500/20 text-red-400
                                         hover:bg-red-500/30 transition-colors disabled:opacity-50"
                            >
                              {deleting === v.id ? '...' : 'Si'}
                            </button>
                            <button
                              onClick={() => setConfirmDelete(null)}
                              className="px-2 py-1 text-[10px] rounded bg-[#1a1a2e] text-[#8888a0]
                                         hover:text-[#e8e8f0] transition-colors"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDelete(v.id)}
                            className="px-2.5 py-1 text-[11px] rounded text-[#555570]
                                       hover:text-red-400 hover:bg-red-500/10 transition-colors ml-auto"
                          >
                            Eliminar
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
