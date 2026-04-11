import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PageLoader } from '../components/ui/Spinner'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Ban, Plus, Trash2, ChevronLeft, ChevronRight, Download, Upload, Search } from 'lucide-react'

const SOURCE_LABELS = {
  manual: { label: 'Manual', color: 'bg-blue-500/15 text-blue-400' },
  user_request: { label: 'Usuario pidio', color: 'bg-yellow-500/15 text-yellow-400' },
  escalation: { label: 'Escalada', color: 'bg-red-500/15 text-red-400' },
  import: { label: 'Import', color: 'bg-purple-500/15 text-purple-400' },
}

export function DNC() {
  const [entries, setEntries] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [newPhone, setNewPhone] = useState('')
  const [newReason, setNewReason] = useState('')
  const [adding, setAdding] = useState(false)
  const [search, setSearch] = useState('')
  const [searchDebounced, setSearchDebounced] = useState('')
  const [showBulk, setShowBulk] = useState(false)
  const [bulkText, setBulkText] = useState('')
  const [bulkReason, setBulkReason] = useState('')
  const [importing, setImporting] = useState(false)
  const toast = useToast()
  const confirmDialog = useConfirm()
  const perPage = 20

  function load() {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: perPage })
    if (searchDebounced) params.set('search', searchDebounced)
    api.get(`/dnc?${params}`)
      .then(res => {
        setEntries(res.data || [])
        setTotal(res.total || 0)
      })
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setSearchDebounced(search)
      setPage(1)
    }, 400)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => { load() }, [page, searchDebounced])

  async function handleExport() {
    try {
      const res = await fetch(`${api.baseURL || ''}/dnc/export`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('jwt') || ''}` },
      })
      if (!res.ok) throw new Error('Error al exportar')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dnc_list.csv'
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Exportado')
    } catch (e) {
      toast.error(e.message)
    }
  }

  async function handleBulkImport(e) {
    e.preventDefault()
    const phones = bulkText.split(/[\n,]/).map(p => p.trim()).filter(Boolean)
    if (phones.length === 0) {
      toast.error('Sin números para importar')
      return
    }
    setImporting(true)
    try {
      const res = await api.post('/dnc/bulk', { phones, reason: bulkReason.trim() || null })
      toast.success(`${res.added} números agregados`)
      setBulkText('')
      setBulkReason('')
      setShowBulk(false)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setImporting(false)
    }
  }

  async function handleAdd(e) {
    e.preventDefault()
    if (!newPhone.trim()) return
    setAdding(true)
    try {
      await api.post('/dnc', { phone: newPhone.trim(), reason: newReason.trim() || null })
      toast.success('Numero agregado a DNC')
      setNewPhone('')
      setNewReason('')
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(id, phone) {
    const ok = await confirmDialog({
      title: 'Eliminar de DNC',
      message: `El numero ${phone} podra volver a recibir llamadas. Continuar?`,
      confirmText: 'Eliminar',
      variant: 'danger',
    })
    if (!ok) return
    try {
      await api.delete(`/dnc/${id}`)
      toast.success('Eliminado de DNC')
      load()
    } catch (e) {
      toast.error(e.message)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  if (loading && page === 1) return <PageLoader />

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Ban size={24} className="text-red-400" />
            Do-Not-Call (DNC)
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Numeros bloqueados para llamadas outbound. Se agregan manualmente o cuando
            el usuario pide explicitamente que no lo llamen.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowBulk(!showBulk)}>
            <Upload size={14} /> Import
          </Button>
          <Button variant="secondary" onClick={handleExport}>
            <Download size={14} /> Export CSV
          </Button>
        </div>
      </div>

      {/* Búsqueda */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <Input
          placeholder="Buscar por número..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Bulk import panel */}
      {showBulk && (
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold text-text-secondary">Importar numeros en masa</h2>
          <form onSubmit={handleBulkImport} className="space-y-3">
            <textarea
              placeholder="Un número por línea o separados por coma&#10;+529991234567&#10;+525512345678"
              value={bulkText}
              onChange={e => setBulkText(e.target.value)}
              className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm font-mono min-h-[120px] focus:outline-none focus:border-accent"
            />
            <Input
              placeholder="Razón para todos (opcional)"
              value={bulkReason}
              onChange={e => setBulkReason(e.target.value)}
            />
            <div className="flex gap-2">
              <Button type="submit" disabled={importing || !bulkText.trim()}>
                {importing ? 'Importando...' : 'Importar'}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setShowBulk(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Formulario individual */}
      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-text-secondary">Agregar numero</h2>
        <form onSubmit={handleAdd} className="flex gap-2 flex-wrap">
          <Input
            placeholder="+529994890531"
            value={newPhone}
            onChange={e => setNewPhone(e.target.value)}
            className="flex-1 min-w-[200px]"
          />
          <Input
            placeholder="Razon (opcional)"
            value={newReason}
            onChange={e => setNewReason(e.target.value)}
            className="flex-1 min-w-[200px]"
          />
          <Button type="submit" disabled={adding || !newPhone.trim()}>
            <Plus size={14} /> Agregar
          </Button>
        </form>
      </Card>

      {/* Lista */}
      {entries.length === 0 ? (
        <Card className="text-center py-12 text-text-muted">
          <Ban size={32} className="mx-auto mb-3 opacity-40" />
          <p>No hay numeros en DNC</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {entries.map(e => {
            const src = SOURCE_LABELS[e.source] || SOURCE_LABELS.manual
            return (
              <Card key={e.id} className="flex items-center gap-4 p-4">
                <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 bg-red-500/15 text-red-400">
                  <Ban size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm font-medium">{e.phone}</span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${src.color}`}>
                      {src.label}
                    </span>
                  </div>
                  {e.reason && (
                    <p className="text-xs text-text-muted mt-1">{e.reason}</p>
                  )}
                  <p className="text-[10px] text-text-muted mt-0.5">
                    Agregado: {new Date(e.created_at).toLocaleString('es-MX')}
                  </p>
                </div>
                <Button variant="danger" size="sm" onClick={() => handleDelete(e.id, e.phone)}>
                  <Trash2 size={14} />
                </Button>
              </Card>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">{total} numeros</span>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft size={14} />
            </Button>
            <span className="text-xs text-text-muted">{page} / {totalPages}</span>
            <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
