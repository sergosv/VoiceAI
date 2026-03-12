import { useEffect, useState } from 'react'
import { Key, Ban, RefreshCw, Loader2 } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useConfirm } from '../../context/ConfirmContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

export function AdminApiKeys() {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [revokingId, setRevokingId] = useState(null)
  const perPage = 50
  const toast = useToast()
  const confirm = useConfirm()

  async function fetchKeys(p = page) {
    try {
      const data = await api.get(`/admin/api-keys?page=${p}&per_page=${perPage}`)
      setKeys(data.data || [])
      setTotal(data.total || 0)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.get(`/admin/api-keys?page=${page}&per_page=${perPage}`)
      .then(data => {
        if (!cancelled) {
          setKeys(data.data || [])
          setTotal(data.total || 0)
        }
      })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [page])

  async function handleRevoke(key) {
    const ok = await confirm({
      title: 'Revocar API key',
      message: `Revocar la key "${key.name || key.key_prefix}" del cliente "${key.client_name}"? Ya no podra usarse para autenticacion.`,
      confirmText: 'Revocar',
      variant: 'danger',
    })
    if (!ok) return
    setRevokingId(key.id)
    try {
      await api.patch(`/admin/api-keys/${key.id}`)
      setKeys(prev => prev.map(k => k.id === key.id ? { ...k, is_active: false } : k))
      toast.success('API key revocada')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setRevokingId(null)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  function fmtDate(d) {
    if (!d) return '--'
    return new Date(d).toLocaleDateString('es-MX', {
      day: '2-digit', month: 'short', year: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <Key size={22} className="text-accent" />
            API Keys
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {total} key{total !== 1 ? 's' : ''} en total
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => { setLoading(true); fetchKeys() }}
        >
          <RefreshCw size={14} className="mr-2 inline" />
          Actualizar
        </Button>
      </div>

      <Card>
        {loading ? <PageLoader /> : keys.length === 0 ? (
          <EmptyState
            icon={Key}
            title="Sin API keys"
            description="No hay API keys creadas en la plataforma."
          />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Cliente</Th>
                  <Th>Nombre</Th>
                  <Th>Key</Th>
                  <Th>Scopes</Th>
                  <Th>Estado</Th>
                  <Th>Creada</Th>
                  <Th>Ultimo uso</Th>
                  <Th className="text-right">Acciones</Th>
                </tr>
              </thead>
              <tbody>
                {keys.map(k => (
                  <tr key={k.id} className="hover:bg-bg-hover/50 transition-colors">
                    <Td>
                      <span className="text-text-primary text-sm">{k.client_name}</span>
                    </Td>
                    <Td>
                      <span className="text-text-secondary text-sm">{k.name || '--'}</span>
                    </Td>
                    <Td>
                      <span className="font-mono text-xs text-text-muted">{k.key_prefix}</span>
                    </Td>
                    <Td>
                      {(k.scopes || []).length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {k.scopes.map(s => (
                            <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent">
                              {s}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-text-muted text-xs">--</span>
                      )}
                    </Td>
                    <Td>
                      <Badge variant={k.is_active ? 'completed' : 'failed'}>
                        {k.is_active ? 'Activa' : 'Revocada'}
                      </Badge>
                    </Td>
                    <Td>
                      <span className="text-text-muted text-xs">{fmtDate(k.created_at)}</span>
                    </Td>
                    <Td>
                      <span className="text-text-muted text-xs">{fmtDate(k.last_used_at)}</span>
                    </Td>
                    <Td>
                      <div className="flex items-center justify-end">
                        {k.is_active && (
                          <button
                            onClick={() => handleRevoke(k)}
                            disabled={revokingId === k.id}
                            className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer disabled:opacity-50"
                            title="Revocar"
                          >
                            {revokingId === k.id
                              ? <Loader2 size={15} className="animate-spin" />
                              : <Ban size={15} />}
                          </button>
                        )}
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>

            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                <span className="text-xs text-text-muted">
                  Pagina {page} de {totalPages}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
