import { useEffect, useState, useRef } from 'react'
import { Upload, Trash2, FileText, DollarSign, HelpCircle, Building, Shield, Users, MapPin, BookOpen, ChevronDown, FileUp } from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Table, Th, Td } from '../components/ui/Table'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'

const KB_CATEGORIES = [
  {
    icon: DollarSign,
    title: 'Servicios y precios',
    desc: 'Lista tus servicios con precios, duración y descripción clara.',
    example: 'Limpieza dental — $800 MXN, duración 45 min, incluye revisión general',
  },
  {
    icon: HelpCircle,
    title: 'Preguntas frecuentes',
    desc: 'Las preguntas que más hacen tus clientes y sus respuestas.',
    example: '¿Aceptan tarjeta? Sí, Visa y Mastercard. También meses sin intereses.',
  },
  {
    icon: Building,
    title: 'Información del negocio',
    desc: 'Dirección, horarios, formas de contacto y estacionamiento.',
    example: 'Calle 60 #500, Col. Centro, Mérida. Lunes a viernes 9-18h. Sábados 9-14h.',
  },
  {
    icon: Shield,
    title: 'Políticas',
    desc: 'Cancelaciones, garantías, devoluciones y condiciones.',
    example: 'Cancelaciones con 24h de anticipación sin cargo. Reagendamos sin costo.',
  },
  {
    icon: Users,
    title: 'Equipo',
    desc: 'Información sobre doctores, especialistas o personal clave.',
    example: 'Dr. García — Ortodoncia, 15 años de experiencia. Atiende L-M-V.',
  },
  {
    icon: MapPin,
    title: 'Contexto local',
    desc: 'Referencias de ubicación y datos que un local conocería.',
    example: 'Frente al parque de Santiago, a 2 cuadras del mercado Lucas de Gálvez.',
  },
]

function KnowledgeBaseGuide({ docCount }) {
  const [open, setOpen] = useState(docCount === 0)

  return (
    <Card className="border-accent/20">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <BookOpen size={18} className="text-accent" />
          <span className="font-semibold text-sm">¿Qué documentos subir a la base de conocimientos?</span>
        </div>
        <ChevronDown size={16} className={`text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {KB_CATEGORIES.map(cat => (
            <div key={cat.title} className="border border-border rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <cat.icon size={16} className="text-accent" />
                <span className="text-sm font-medium">{cat.title}</span>
              </div>
              <p className="text-xs text-text-secondary">{cat.desc}</p>
              <p className="text-xs text-text-muted italic bg-bg-hover/50 rounded px-2 py-1">
                Ej: "{cat.example}"
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export function Documents() {
  const { user } = useAuth()
  const toast = useToast()
  const confirm = useConfirm()
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
      .catch(err => toast.error(err.message))
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
    const ok = await confirm({
      title: 'Eliminar documento',
      message: '¿Eliminar este documento? Se quitará de la base de conocimientos.',
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
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

      <KnowledgeBaseGuide docCount={docs.length} />

      <Card>
        {loading ? <PageLoader /> : docs.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Sin documentos"
            description="Sube archivos con informacion de tu negocio (servicios, precios, FAQs) para que tu agente pueda responder preguntas de tus clientes."
            action={() => fileRef.current?.click()}
            actionLabel="Subir documento"
            actionIcon={FileUp}
          />
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
