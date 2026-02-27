import { useEffect, useState, useRef } from 'react'
import { Upload, Trash2, FileText } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'

export function Documents() {
  const { user } = useAuth()
  const toast = useToast()
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [clientId, setClientId] = useState(null)
  const fileRef = useRef()

  function loadDocs() {
    setLoading(true)
    const params = clientId ? `?client_id=${clientId}` : ''
    api.get(`/documents${params}`)
      .then(setDocs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(loadDocs, [clientId])

  // Para admin: determinar el client_id efectivo para upload
  const effectiveClientId = user?.role === 'client' ? user.client_id : clientId
  const canUpload = !!effectiveClientId

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('description', file.name)
      if (effectiveClientId) fd.append('client_id', effectiveClientId)
      await api.upload('/documents', fd)
      loadDocs()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleDelete(id) {
    if (!confirm('¿Eliminar documento?')) return
    try {
      await api.delete(`/documents/${id}`)
      setDocs(docs.filter(d => d.id !== id))
      toast.success('Documento eliminado')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Documentos</h1>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={setClientId} />
          <input ref={fileRef} type="file" className="hidden" onChange={handleUpload} accept=".pdf,.txt,.md,.csv,.doc,.docx" />
          <Button
            onClick={() => fileRef.current?.click()}
            disabled={uploading || !canUpload}
            title={!canUpload ? 'Selecciona un cliente primero' : ''}
          >
            <Upload size={16} className="mr-2 inline" />
            {uploading ? 'Subiendo...' : 'Subir documento'}
          </Button>
        </div>
      </div>

      {user?.role === 'admin' && !clientId && (
        <p className="text-sm text-text-muted">Selecciona un cliente para subir documentos.</p>
      )}

      <Card>
        {loading ? <PageLoader /> : docs.length === 0 ? (
          <div className="text-center py-12">
            <FileText size={40} className="mx-auto text-text-muted mb-3" />
            <p className="text-text-muted">Sin documentos. Sube archivos a tu knowledge base.</p>
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Archivo</Th>
                <Th>Tipo</Th>
                <Th>Tamaño</Th>
                <Th>Estado</Th>
                <Th>Fecha</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} className="hover:bg-bg-hover/50">
                  <Td className="font-medium">{doc.filename}</Td>
                  <Td><span className="font-mono text-xs uppercase">{doc.file_type}</span></Td>
                  <Td className="text-text-secondary text-xs">{((doc.file_size_bytes || 0) / 1024).toFixed(1)} KB</Td>
                  <Td><Badge variant={doc.indexing_status}>{doc.indexing_status}</Badge></Td>
                  <Td className="text-text-secondary text-xs">
                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString('es-MX') : '-'}
                  </Td>
                  <Td>
                    <button onClick={() => handleDelete(doc.id)} className="text-text-muted hover:text-danger cursor-pointer">
                      <Trash2 size={16} />
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}
