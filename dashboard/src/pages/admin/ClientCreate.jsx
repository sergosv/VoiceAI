import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input, Select } from '../../components/ui/Input'

export function ClientCreate() {
  const navigate = useNavigate()
  const toast = useToast()
  const [voices, setVoices] = useState([])
  const [form, setForm] = useState({
    name: '',
    slug: '',
    business_type: 'generic',
    agent_name: 'María',
    voice_key: 'es_female_warm',
    language: 'es',
    owner_email: '',
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/voices').then(setVoices).catch(console.error)
  }, [])

  function updateField(field, value) {
    setForm(f => ({ ...f, [field]: value }))
    if (field === 'name' && !form.slug) {
      const slug = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
      setForm(f => ({ ...f, slug }))
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const created = await api.post('/clients', form)
      toast.success(`Cliente ${created.name} creado`)
      navigate(`/admin/clients/${created.id}`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => navigate('/admin/clients')}>
          <ArrowLeft size={16} />
        </Button>
        <h1 className="text-2xl font-bold">Nuevo cliente</h1>
      </div>

      <form onSubmit={handleSubmit}>
        <Card className="space-y-4 max-w-lg">
          <Input label="Nombre del negocio" value={form.name} onChange={e => updateField('name', e.target.value)} required />
          <Input label="Slug" value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value }))} required placeholder="dr-garcia" />
          <Select
            label="Tipo de negocio"
            value={form.business_type}
            onChange={e => setForm(f => ({ ...f, business_type: e.target.value }))}
            options={[
              { value: 'generic', label: 'Genérico' },
              { value: 'dental', label: 'Dental' },
              { value: 'gym', label: 'Gimnasio' },
              { value: 'restaurant', label: 'Restaurante' },
              { value: 'realestate', label: 'Inmobiliaria' },
            ]}
          />
          <Input label="Nombre del agente" value={form.agent_name} onChange={e => setForm(f => ({ ...f, agent_name: e.target.value }))} />
          <Select
            label="Voz"
            value={form.voice_key}
            onChange={e => setForm(f => ({ ...f, voice_key: e.target.value }))}
            options={voices.map(v => ({ value: v.key, label: `${v.name} — ${v.description}` }))}
          />
          <Select
            label="Idioma"
            value={form.language}
            onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
            options={[
              { value: 'es', label: 'Español' },
              { value: 'en', label: 'English' },
              { value: 'es-en', label: 'Bilingüe' },
            ]}
          />
          <Input label="Email del dueño" type="email" value={form.owner_email} onChange={e => setForm(f => ({ ...f, owner_email: e.target.value }))} />

          <Button type="submit" disabled={saving} className="w-full">
            {saving ? 'Creando...' : 'Crear cliente'}
          </Button>
        </Card>
      </form>
    </div>
  )
}
