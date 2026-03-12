import { useEffect, useState } from 'react'
import {
  LayoutTemplate, TrendingUp, Hash, Star, RefreshCw, Loader2,
  Power, PowerOff, Phone, PhoneOutgoing,
} from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'

export function AdminTemplates() {
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(null)
  const toast = useToast()

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.get('/templates/search'),
      api.get('/templates/admin/stats').catch(() => null),
    ])
      .then(([tpls, st]) => {
        if (cancelled) return
        setTemplates(tpls?.templates || tpls || [])
        setStats(st)
      })
      .catch(err => { if (!cancelled) toast.error(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function toggleActive(template) {
    setToggling(template.id)
    try {
      const updated = await api.patch(`/templates/${template.id}`, {
        is_active: !template.is_active,
      })
      setTemplates(prev =>
        prev.map(t => t.id === template.id ? { ...t, is_active: !t.is_active, ...updated } : t)
      )
      toast.success(`Template "${template.name}" ${!template.is_active ? 'activado' : 'desactivado'}`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setToggling(null)
    }
  }

  if (loading) return <PageLoader />

  const totalTemplates = templates.length
  const totalUses = stats?.total_uses ?? templates.reduce((sum, t) => sum + (t.usage_count || 0), 0)
  const mostPopular = stats?.most_popular
    || [...templates].sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))[0]?.name
    || '--'
  const activeCount = templates.filter(t => t.is_active !== false).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <LayoutTemplate size={22} className="text-accent" />
            Templates
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Gestiona los templates de agentes disponibles
          </p>
        </div>
      </div>

      {/* Stats summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <Hash size={20} className="text-accent mx-auto mb-1" />
          <p className="text-2xl font-bold text-text-primary">{totalTemplates}</p>
          <p className="text-[10px] text-text-muted uppercase tracking-wider">Total Templates</p>
        </Card>
        <Card className="text-center">
          <Power size={20} className="text-green-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-green-400">{activeCount}</p>
          <p className="text-[10px] text-text-muted uppercase tracking-wider">Activos</p>
        </Card>
        <Card className="text-center">
          <TrendingUp size={20} className="text-purple-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-purple-400">{totalUses}</p>
          <p className="text-[10px] text-text-muted uppercase tracking-wider">Usos Totales</p>
        </Card>
        <Card className="text-center">
          <Star size={20} className="text-yellow-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-yellow-400 truncate">{mostPopular}</p>
          <p className="text-[10px] text-text-muted uppercase tracking-wider">Mas Popular</p>
        </Card>
      </div>

      {/* Templates table */}
      <Card>
        {templates.length === 0 ? (
          <EmptyState
            icon={LayoutTemplate}
            title="Sin templates"
            description="No hay templates creados. Crea templates desde la API."
          />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Nombre</Th>
                <Th>Vertical</Th>
                <Th>Direccion</Th>
                <Th>Usos</Th>
                <Th>Estado</Th>
                <Th className="text-right">Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {templates.map(t => (
                <tr key={t.id} className="hover:bg-bg-hover/50 transition-colors">
                  <Td>
                    <div>
                      <span className="font-medium text-text-primary">{t.name}</span>
                      {t.description && (
                        <p className="text-[11px] text-text-muted truncate max-w-[300px]">
                          {t.description}
                        </p>
                      )}
                    </div>
                  </Td>
                  <Td>
                    <Badge>{t.vertical || t.category || '--'}</Badge>
                  </Td>
                  <Td>
                    <Badge variant={t.direction === 'outbound' ? 'outbound' : 'inbound'}>
                      <span className="inline-flex items-center gap-1">
                        {t.direction === 'outbound'
                          ? <PhoneOutgoing size={10} />
                          : <Phone size={10} />}
                        {t.direction || 'inbound'}
                      </span>
                    </Badge>
                  </Td>
                  <Td>
                    <span className="text-text-primary font-mono text-sm">
                      {t.usage_count || 0}
                    </span>
                  </Td>
                  <Td>
                    <Badge variant={t.is_active !== false ? 'completed' : 'failed'}>
                      {t.is_active !== false ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end">
                      <button
                        onClick={() => toggleActive(t)}
                        disabled={toggling === t.id}
                        className={`p-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 ${
                          t.is_active !== false
                            ? 'text-success hover:bg-success/10'
                            : 'text-text-muted hover:bg-bg-hover'
                        }`}
                        title={t.is_active !== false ? 'Desactivar' : 'Activar'}
                      >
                        {toggling === t.id
                          ? <Loader2 size={15} className="animate-spin" />
                          : t.is_active !== false
                            ? <Power size={15} />
                            : <PowerOff size={15} />}
                      </button>
                    </div>
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
