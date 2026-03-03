import { useEffect, useState } from 'react'
import { Save, DollarSign, Percent, ArrowRight } from 'lucide-react'
import { api } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { PageLoader } from '../../components/ui/Spinner'

const PROVIDER_COSTS = [
  { key: 'cost_twilio_per_min', label: 'Twilio (telefonía)' },
  { key: 'cost_stt_per_min', label: 'Deepgram (STT)' },
  { key: 'cost_llm_per_min', label: 'Gemini (LLM)' },
  { key: 'cost_tts_per_min', label: 'Cartesia (TTS)' },
  { key: 'cost_livekit_per_min', label: 'LiveKit Cloud' },
  { key: 'cost_mcp_per_min', label: 'MCP / Tools (promedio)' },
]

export function PricingConfig() {
  const toast = useToast()
  const [config, setConfig] = useState(null)
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/billing/admin/pricing'),
      api.get('/billing/packages'),
    ]).then(([cfg, pkgs]) => {
      setConfig(cfg)
      setPackages(pkgs)
    }).catch(err => {
      console.error('Pricing load error:', err)
      toast.error('Error cargando configuración de precios')
    }).finally(() => setLoading(false))
  }, [])

  // Cálculos en tiempo real
  const costPerMin = config
    ? PROVIDER_COSTS.reduce((sum, p) => sum + parseFloat(config[p.key] || 0), 0)
    : 0

  const margin = config ? parseFloat(config.profit_margin || 0.75) : 0.75
  const pricePerCredit = margin < 1 ? costPerMin / (1 - margin) : 0
  const profitPerCredit = pricePerCredit - costPerMin

  function updateConfig(key, value) {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  async function saveAndRecalculate() {
    setSaving(true)
    try {
      const payload = {}
      for (const p of PROVIDER_COSTS) {
        payload[p.key] = parseFloat(config[p.key])
      }
      payload.profit_margin = parseFloat(config.profit_margin)
      payload.free_credits_new_account = parseInt(config.free_credits_new_account)
      payload.usd_to_mxn_rate = parseFloat(config.usd_to_mxn_rate)

      const data = await api.patch('/billing/admin/pricing', payload)
      if (data.packages) {
        setPackages(data.packages)
      }
      toast.success('Precios actualizados y paquetes recalculados')
    } catch (err) {
      toast.error(err.message || 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <PageLoader />
  if (!config) return null

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Configuración de Precios</h1>

      {/* 3 Cards resumen */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-red-500/5 border-red-500/20">
          <div className="text-sm text-red-400">Costo base / minuto</div>
          <div className="text-2xl font-bold text-red-400 mt-1">
            ${costPerMin.toFixed(4)} USD
          </div>
          <div className="text-xs text-text-muted mt-1">Lo que pagas a proveedores</div>
        </Card>
        <Card className="bg-green-500/5 border-green-500/20">
          <div className="text-sm text-green-400">Precio al cliente / minuto</div>
          <div className="text-2xl font-bold text-green-400 mt-1">
            ${pricePerCredit.toFixed(4)} USD
          </div>
          <div className="text-xs text-text-muted mt-1">Lo que cobra al cliente</div>
        </Card>
        <Card className="bg-accent/5 border-accent/20">
          <div className="text-sm text-accent">Tu ganancia / minuto</div>
          <div className="text-2xl font-bold text-accent mt-1">
            ${profitPerCredit.toFixed(4)} USD
          </div>
          <div className="text-xs text-text-muted mt-1">{(margin * 100).toFixed(0)}% de margen</div>
        </Card>
      </div>

      {/* Slider de margen */}
      <Card>
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Percent size={20} className="text-accent" />
          Margen de ganancia
        </h2>
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-muted">50%</span>
          <input
            type="range"
            min="0.50"
            max="0.90"
            step="0.01"
            value={margin}
            onChange={e => updateConfig('profit_margin', e.target.value)}
            className="flex-1 h-2 rounded-lg appearance-none cursor-pointer accent-accent bg-bg-hover"
          />
          <span className="text-sm text-text-muted">90%</span>
          <span className="text-2xl font-bold w-20 text-center text-accent">
            {(margin * 100).toFixed(0)}%
          </span>
        </div>
        <p className="text-xs text-text-muted mt-2">
          Mueve el slider y los paquetes se recalculan al guardar.
          Los clientes existentes no se afectan.
        </p>
      </Card>

      {/* Costos por proveedor */}
      <Card>
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <DollarSign size={20} className="text-red-400" />
          Costos por proveedor (USD / minuto)
        </h2>
        <p className="text-xs text-text-muted mb-4">
          Actualiza estos valores si cambian las tarifas de tus proveedores.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {PROVIDER_COSTS.map(item => (
            <div key={item.key}>
              <label className="text-xs text-text-muted block mb-1">{item.label}</label>
              <input
                type="number"
                step="0.001"
                min="0"
                value={config[item.key] || 0}
                onChange={e => updateConfig(item.key, e.target.value)}
                className="w-full bg-bg-primary border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent transition-colors"
              />
            </div>
          ))}
        </div>
        <div className="mt-4 pt-4 border-t border-border flex justify-between items-center">
          <span className="text-sm text-text-muted">Costo total por minuto:</span>
          <span className="text-lg font-bold text-red-400">${costPerMin.toFixed(4)} USD</span>
        </div>
      </Card>

      {/* Tipo de cambio + créditos de bienvenida */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <h2 className="text-sm font-semibold text-text-secondary mb-3">Tipo de cambio</h2>
          <div className="flex items-center gap-3">
            <span className="text-sm">1 USD =</span>
            <input
              type="number"
              step="0.01"
              min="1"
              value={config.usd_to_mxn_rate || 20}
              onChange={e => updateConfig('usd_to_mxn_rate', e.target.value)}
              className="bg-bg-primary border border-border rounded-lg px-3 py-2 w-28 text-sm focus:outline-none focus:border-accent"
            />
            <span className="text-sm">MXN</span>
          </div>
        </Card>
        <Card>
          <h2 className="text-sm font-semibold text-text-secondary mb-3">Créditos de bienvenida</h2>
          <div className="flex items-center gap-3">
            <span className="text-sm">Cuentas nuevas reciben:</span>
            <input
              type="number"
              step="1"
              min="0"
              value={config.free_credits_new_account || 10}
              onChange={e => updateConfig('free_credits_new_account', e.target.value)}
              className="bg-bg-primary border border-border rounded-lg px-3 py-2 w-20 text-sm focus:outline-none focus:border-accent"
            />
            <span className="text-sm">créditos</span>
          </div>
        </Card>
      </div>

      {/* Vista previa paquetes */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Vista previa de paquetes</h2>
        <p className="text-xs text-text-muted mb-4">
          Estos precios se recalculan en tiempo real. Click en "Guardar" para aplicar.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 font-medium text-text-muted">Paquete</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">Créditos</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">Descuento</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">$/min</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">Precio USD</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">Precio MXN</th>
                <th className="text-right py-2 px-3 font-medium text-text-muted">Ganancia</th>
              </tr>
            </thead>
            <tbody>
              {packages.map(pkg => {
                const effectivePrice = pricePerCredit * (1 - (pkg.volume_discount || 0))
                const pkgPriceUsd = pkg.credits * effectivePrice
                const pkgPriceMxn = pkgPriceUsd * parseFloat(config.usd_to_mxn_rate || 20)
                const pkgProfit = pkgPriceUsd - (costPerMin * pkg.credits)

                return (
                  <tr key={pkg.id} className="border-b border-border/50 hover:bg-bg-hover transition-colors">
                    <td className="py-2 px-3 font-medium">
                      {pkg.name}
                      {pkg.is_popular && (
                        <span className="ml-2 text-xs text-accent">Popular</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">{pkg.credits?.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right">
                      {pkg.volume_discount > 0 ? `${(pkg.volume_discount * 100).toFixed(0)}%` : '-'}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">${effectivePrice.toFixed(4)}</td>
                    <td className="py-2 px-3 text-right font-mono font-medium">${pkgPriceUsd.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right font-mono">${pkgPriceMxn.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right font-mono text-green-400 font-medium">${pkgProfit.toFixed(2)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Botón guardar */}
      <Button onClick={saveAndRecalculate} disabled={saving} className="w-full py-3">
        <Save size={16} className="mr-2 inline" />
        {saving ? 'Guardando y recalculando...' : 'Guardar y recalcular paquetes'}
      </Button>
      <p className="text-xs text-text-muted text-center">
        Los clientes existentes no se afectan. Los nuevos precios aplican solo para compras futuras.
      </p>
    </div>
  )
}
