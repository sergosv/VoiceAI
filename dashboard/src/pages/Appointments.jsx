import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Badge } from '../components/ui/Badge'
import { Modal } from '../components/ui/Modal'
import { PageLoader } from '../components/ui/Spinner'
import { ClientSelector } from '../components/ClientSelector'
import { useToast } from '../context/ToastContext'
import { useConfirm } from '../context/ConfirmContext'
import { Calendar, Plus, Clock, ChevronLeft, ChevronRight } from 'lucide-react'

const statusColors = {
  confirmed: 'bg-success/20 text-success',
  cancelled: 'bg-danger/20 text-danger',
  completed: 'bg-accent/20 text-accent',
  no_show: 'bg-warning/20 text-warning',
}

const statusLabels = {
  confirmed: 'Confirmada',
  cancelled: 'Cancelada',
  completed: 'Completada',
  no_show: 'No asistió',
}

function getWeekDates(baseDate) {
  const d = new Date(baseDate)
  const day = d.getDay()
  const monday = new Date(d)
  monday.setDate(d.getDate() - ((day + 6) % 7))
  const dates = []
  for (let i = 0; i < 7; i++) {
    const date = new Date(monday)
    date.setDate(monday.getDate() + i)
    dates.push(date)
  }
  return dates
}

const dayNames = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const hours = Array.from({ length: 12 }, (_, i) => i + 8) // 8:00 - 19:00

export function Appointments() {
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState(null)
  const [weekBase, setWeekBase] = useState(new Date())
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const toast = useToast()
  const confirmDialog = useConfirm()

  const weekDates = getWeekDates(weekBase)
  const dateFrom = weekDates[0].toISOString().slice(0, 10)
  const dateTo = weekDates[6].toISOString().slice(0, 10)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ per_page: 100, date_from: dateFrom, date_to: dateTo })
    if (statusFilter) params.set('status', statusFilter)
    if (clientId) params.set('client_id', clientId)
    api.get(`/appointments?${params}`)
      .then(setAppointments)
      .catch(e => toast.error(e.message))
      .finally(() => setLoading(false))
  }, [dateFrom, dateTo, statusFilter, clientId])

  function shiftWeek(dir) {
    setWeekBase(prev => {
      const d = new Date(prev)
      d.setDate(d.getDate() + dir * 7)
      return d
    })
  }

  function goToday() {
    setWeekBase(new Date())
  }

  async function handleStatusChange(id, newStatus) {
    try {
      const updated = await api.patch(`/appointments/${id}`, { status: newStatus })
      setAppointments(prev => prev.map(a => a.id === id ? updated : a))
      toast.success(`Cita ${statusLabels[newStatus]?.toLowerCase()}`)
    } catch (err) {
      toast.error(err.message)
    }
  }

  // Formatear fecha en zona local (YYYY-MM-DD) — consistente con getHours()
  function toLocalDateStr(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  // Agrupar citas por día y hora (ambos en timezone local del navegador)
  function getAppointmentsForSlot(dayDate, hour) {
    const dayStr = toLocalDateStr(dayDate)
    return appointments.filter(a => {
      const start = new Date(a.start_time)
      return toLocalDateStr(start) === dayStr && start.getHours() === hour
    })
  }

  const today = toLocalDateStr(new Date())

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Calendar size={24} /> Citas
        </h1>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={v => setClientId(v)} />
          <Button onClick={() => setShowCreate(true)}>
            <Plus size={16} className="mr-1" /> Nueva cita
          </Button>
        </div>
      </div>

      {/* Filtros y navegación de semana */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => shiftWeek(-1)}><ChevronLeft size={16} /></Button>
          <Button variant="secondary" onClick={goToday} className="text-xs">Hoy</Button>
          <Button variant="secondary" onClick={() => shiftWeek(1)}><ChevronRight size={16} /></Button>
          <span className="text-sm text-text-muted ml-2">
            {weekDates[0].toLocaleDateString('es-MX', { month: 'short', day: 'numeric' })} — {weekDates[6].toLocaleDateString('es-MX', { month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
        </div>
        <div className="flex gap-2">
          {['', 'confirmed', 'completed', 'cancelled', 'no_show'].map(s => (
            <Button
              key={s}
              variant={statusFilter === s ? 'primary' : 'secondary'}
              onClick={() => setStatusFilter(s)}
              className="text-xs"
            >
              {s ? statusLabels[s] : 'Todas'}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <PageLoader />
      ) : (
        <Card className="overflow-x-auto">
          {/* Calendario semanal tipo grid */}
          <div className="grid grid-cols-[60px_repeat(7,1fr)] min-w-[800px]">
            {/* Header */}
            <div className="border-b border-border p-2" />
            {weekDates.map((d, i) => {
              const isToday = d.toISOString().slice(0, 10) === today
              return (
                <div
                  key={i}
                  className={`border-b border-l border-border p-2 text-center ${isToday ? 'bg-accent/5' : ''}`}
                >
                  <div className="text-xs text-text-muted">{dayNames[i]}</div>
                  <div className={`text-sm font-semibold ${isToday ? 'text-accent' : ''}`}>
                    {d.getDate()}
                  </div>
                </div>
              )
            })}

            {/* Rows por hora */}
            {hours.map(hour => (
              <>
                <div key={`h-${hour}`} className="border-b border-border p-1 text-xs text-text-muted text-right pr-2 pt-2">
                  {String(hour).padStart(2, '0')}:00
                </div>
                {weekDates.map((d, i) => {
                  const slots = getAppointmentsForSlot(d, hour)
                  return (
                    <div
                      key={`${hour}-${i}`}
                      className="border-b border-l border-border p-1 min-h-[50px]"
                    >
                      {slots.map(a => (
                        <div
                          key={a.id}
                          className={`text-[10px] rounded px-1.5 py-0.5 mb-0.5 cursor-pointer truncate ${statusColors[a.status] || 'bg-bg-hover text-text-secondary'}`}
                          title={`${a.title} (${statusLabels[a.status]})`}
                          onClick={async () => {
                            const next = a.status === 'confirmed' ? 'completed' : 'confirmed'
                            const ok = await confirmDialog({
                              title: 'Cambiar estado',
                              message: `¿Cambiar cita a "${statusLabels[next]}"?`,
                              confirmText: 'Cambiar',
                              variant: 'info',
                            })
                            if (ok) handleStatusChange(a.id, next)
                          }}
                        >
                          <span className="font-medium">{new Date(a.start_time).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}</span>{' '}
                          {a.title}
                        </div>
                      ))}
                    </div>
                  )
                })}
              </>
            ))}
          </div>
        </Card>
      )}

      {/* Lista de próximas citas */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Próximas citas</h2>
        {appointments.filter(a => a.status === 'confirmed').length === 0 ? (
          <p className="text-text-muted text-center py-4">No hay citas confirmadas esta semana</p>
        ) : (
          <div className="space-y-2">
            {appointments
              .filter(a => a.status === 'confirmed')
              .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
              .map(a => (
                <div key={a.id} className="flex items-center justify-between p-3 rounded-lg bg-bg-primary border border-border/50">
                  <div>
                    <p className="font-medium text-sm">{a.title}</p>
                    <p className="text-xs text-text-muted flex items-center gap-1">
                      <Clock size={12} />
                      {new Date(a.start_time).toLocaleString('es-MX', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                      {' — '}
                      {new Date(a.end_time).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    {a.description && <p className="text-xs text-text-secondary mt-1">{a.description}</p>}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="secondary" className="text-xs" onClick={() => handleStatusChange(a.id, 'completed')}>
                      Completar
                    </Button>
                    <Button variant="secondary" className="text-xs text-danger" onClick={() => handleStatusChange(a.id, 'cancelled')}>
                      Cancelar
                    </Button>
                  </div>
                </div>
              ))}
          </div>
        )}
      </Card>

      {/* Modal crear cita */}
      {showCreate && (
        <CreateAppointmentModal
          onClose={() => setShowCreate(false)}
          onCreated={a => {
            setAppointments(prev => [...prev, a])
            setShowCreate(false)
            toast.success('Cita creada')
          }}
        />
      )}
    </div>
  )
}

function CreateAppointmentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    date: '',
    startTime: '09:00',
    endTime: '10:00',
  })
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.title || !form.date) return toast.error('Título y fecha requeridos')
    setSaving(true)
    try {
      // Crear Date en zona local del navegador para obtener offset correcto
      const startLocal = new Date(`${form.date}T${form.startTime}`)
      const endLocal = new Date(`${form.date}T${form.endTime}`)
      const tzOffset = -startLocal.getTimezoneOffset()
      const tzSign = tzOffset >= 0 ? '+' : '-'
      const tzH = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0')
      const tzM = String(Math.abs(tzOffset) % 60).padStart(2, '0')
      const tz = `${tzSign}${tzH}:${tzM}`
      const start_time = `${form.date}T${form.startTime}:00${tz}`
      const end_time = `${form.date}T${form.endTime}:00${tz}`
      const created = await api.post('/appointments', {
        title: form.title,
        description: form.description || null,
        start_time,
        end_time,
      })
      onCreated(created)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={true} title="Nueva cita" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Título *" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} required />
        <Input label="Descripción" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
        <Input label="Fecha *" type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} required />
        <div className="grid grid-cols-2 gap-4">
          <Input label="Hora inicio" type="time" value={form.startTime} onChange={e => setForm(f => ({ ...f, startTime: e.target.value }))} />
          <Input label="Hora fin" type="time" value={form.endTime} onChange={e => setForm(f => ({ ...f, endTime: e.target.value }))} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" type="button" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Crear'}</Button>
        </div>
      </form>
    </Modal>
  )
}
