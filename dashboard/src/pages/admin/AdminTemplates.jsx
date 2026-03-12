import { useEffect, useState } from 'react'
import {
  LayoutTemplate, TrendingUp, Hash, Star, RefreshCw, Loader2,
  Power, PowerOff, Phone, PhoneOutgoing, Plus, Pencil, Save,
} from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Table, Th, Td } from '../../components/ui/Table'
import { PageLoader } from '../../components/ui/Spinner'
import { EmptyState } from '../../components/EmptyState'
import { Modal } from '../../components/ui/Modal'
import { Input, Textarea, Select } from '../../components/ui/Input'

const VERTICAL_OPTIONS = [
  { value: '', label: 'Seleccionar...' },
  { value: 'generic', label: 'Genérico' },
  { value: 'dental', label: 'Dental' },
  { value: 'salud', label: 'Médico / Salud' },
  { value: 'servicios', label: 'Legal / Servicios' },
  { value: 'restaurantes', label: 'Restaurante' },
  { value: 'inmobiliaria', label: 'Inmobiliaria' },
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'educacion', label: 'Educación' },
  { value: 'gimnasios', label: 'Fitness' },
  { value: 'salon', label: 'Salón' },
]

const DIRECTION_OPTIONS = [
  { value: 'inbound', label: 'Inbound' },
  { value: 'outbound', label: 'Outbound' },
]

const EMPTY_FORM = {
  name: '',
  description: '',
  vertical_slug: '',
  direction: 'inbound',
  objective: '',
  greeting: '',
  is_active: true,
}

export function AdminTemplates() {
  const [templates, setTemplates] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  function fetchTemplates() {
    setLoading(true)
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
  }

  useEffect(() => {
    const cleanup = fetchTemplates()
    return cleanup
  }, [])

  async function toggleActive(template) {
    setToggling(template.id)
    try {
      const updated = await api.patch(`/templates/admin/templates/${template.id}`, {
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

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setModalOpen(true)
  }

  function openEdit(template) {
    setEditing(template)
    setForm({
      name: template.name || '',
      description: template.description || '',
      vertical_slug: template.vertical_slug || '',
      direction: template.direction || 'inbound',
      objective: template.objective || '',
      greeting: template.greeting || '',
      is_active: template.is_active !== false,
    })
    setModalOpen(true)
  }

  function closeModal() {
    setModalOpen(false)
    setEditing(null)
    setForm(EMPTY_FORM)
  }

  function handleChange(field, value) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      toast.error('El nombre es requerido')
      return
    }

    setSaving(true)
    try {
      if (editing) {
        // Solo enviar campos que cambiaron
        const changes = {}
        if (form.name !== (editing.name || '')) changes.name = form.name
        if (form.description !== (editing.description || '')) changes.description = form.description
        if (form.vertical_slug !== (editing.vertical_slug || '')) changes.vertical_slug = form.vertical_slug || null
        if (form.direction !== (editing.direction || 'inbound')) changes.direction = form.direction
        if (form.objective !== (editing.objective || '')) changes.objective = form.objective
        if (form.greeting !== (editing.greeting || '')) changes.greeting = form.greeting
        if (form.is_active !== (editing.is_active !== false)) changes.is_active = form.is_active

        if (Object.keys(changes).length === 0) {
          toast.info('No hay cambios para guardar')
          closeModal()
          return
        }

        await api.patch(`/templates/admin/templates/${editing.id}`, changes)
        toast.success(`Template "${form.name}" actualizado`)
      } else {
        const payload = {
          name: form.name.trim(),
          direction: form.direction,
          is_active: form.is_active,
        }
        if (form.description.trim()) payload.description = form.description.trim()
        if (form.vertical_slug) payload.vertical_slug = form.vertical_slug
        if (form.objective.trim()) payload.objective = form.objective.trim()
        if (form.greeting.trim()) payload.greeting = form.greeting.trim()

        await api.post('/templates/admin/templates', payload)
        toast.success(`Template "${form.name}" creado`)
      }

      closeModal()
      fetchTemplates()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
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
        <Button onClick={openCreate}>
          <Plus size={16} />
          Crear Template
        </Button>
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
            description="No hay templates creados. Usa el botón Crear Template para empezar."
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
                    <Badge>{t.vertical_slug || t.vertical || t.category || '--'}</Badge>
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
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(t)}
                        className="p-1.5 rounded-lg transition-colors cursor-pointer text-text-muted hover:text-accent hover:bg-accent/10"
                        title="Editar"
                      >
                        <Pencil size={15} />
                      </button>
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

      {/* Create / Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={closeModal}
        title={editing ? 'Editar Template' : 'Crear Template'}
        maxWidth="max-w-2xl"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nombre *"
            placeholder="Ej: Calificador de Leads Dental"
            value={form.name}
            onChange={e => handleChange('name', e.target.value)}
            required
          />

          <Textarea
            label="Descripción"
            placeholder="Breve descripción del template..."
            value={form.description}
            onChange={e => handleChange('description', e.target.value)}
            rows={2}
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Vertical / Categoría"
              options={VERTICAL_OPTIONS}
              value={form.vertical_slug}
              onChange={e => handleChange('vertical_slug', e.target.value)}
            />
            <Select
              label="Dirección"
              options={DIRECTION_OPTIONS}
              value={form.direction}
              onChange={e => handleChange('direction', e.target.value)}
            />
          </div>

          <Textarea
            label="System Prompt / Objetivo"
            placeholder="Describe el objetivo y comportamiento del agente..."
            value={form.objective}
            onChange={e => handleChange('objective', e.target.value)}
            rows={5}
            className="min-h-[140px]"
          />

          <Textarea
            label="Greeting"
            placeholder="Mensaje de bienvenida del agente..."
            value={form.greeting}
            onChange={e => handleChange('greeting', e.target.value)}
            rows={3}
          />

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={e => handleChange('is_active', e.target.checked)}
              className="w-4 h-4 rounded border-border bg-bg-secondary text-accent focus:ring-accent/50"
            />
            <span className="text-sm text-text-secondary">Template activo</span>
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="ghost" onClick={closeModal}>
              Cancelar
            </Button>
            <Button type="submit" disabled={saving}>
              {saving
                ? <Loader2 size={16} className="animate-spin" />
                : <Save size={16} />}
              {editing ? 'Guardar Cambios' : 'Crear Template'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
