import { useEffect, useState } from 'react'
import { CreditCard, TrendingUp, TrendingDown, Gift, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { Card } from '../components/ui/Card'
import { PageLoader } from '../components/ui/Spinner'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('es-MX', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function typeLabel(type) {
  switch (type) {
    case 'purchase': return 'Compra'
    case 'consumption': return 'Consumo'
    case 'gift': return 'Regalo'
    case 'refund': return 'Reembolso'
    case 'adjustment': return 'Ajuste'
    default: return type
  }
}

function typeBadgeClass(type) {
  switch (type) {
    case 'purchase': return 'bg-green-500/20 text-green-400'
    case 'consumption': return 'bg-red-500/20 text-red-400'
    case 'gift': return 'bg-purple-500/20 text-purple-400'
    case 'refund': return 'bg-yellow-500/20 text-yellow-400'
    default: return 'bg-bg-hover text-text-secondary'
  }
}

function txDetail(tx) {
  if (tx.type === 'purchase') {
    return `${tx.currency} $${tx.amount_paid} via ${tx.payment_provider}`
  }
  if (tx.type === 'consumption' && tx.duration_seconds) {
    return `${Math.round(tx.duration_seconds / 60)} min llamada`
  }
  return tx.reason || ''
}

export function Billing() {
  const { user } = useAuth()
  const [balance, setBalance] = useState(null)
  const [packages, setPackages] = useState([])
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [purchasing, setPurchasing] = useState(null)

  const clientId = user?.client_id

  useEffect(() => {
    if (!clientId) { setLoading(false); return }
    Promise.all([
      api.get('/billing/balance'),
      api.get('/billing/packages'),
      api.get('/billing/transactions'),
    ]).then(([bal, pkgs, txs]) => {
      setBalance(bal)
      setPackages(pkgs)
      setTransactions(txs)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [clientId])

  async function handlePurchase(packageId, paymentMethod) {
    setPurchasing(packageId + paymentMethod)
    try {
      const data = await api.post('/billing/purchase', {
        client_id: clientId,
        package_id: packageId,
        payment_method: paymentMethod,
      })
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    } catch (err) {
      console.error('Purchase error:', err)
      alert('Error al procesar compra. Intenta de nuevo.')
    } finally {
      setPurchasing(null)
    }
  }

  if (loading) return <PageLoader />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Créditos y facturación</h1>

      {/* Balance actual */}
      <div className="bg-gradient-to-r from-accent/20 to-accent/5 border border-accent/30 rounded-xl p-6">
        <div className="text-sm text-text-secondary">Tu balance actual</div>
        <div className="text-4xl font-bold mt-1 text-accent">
          {balance?.balance?.toFixed(0) || 0} créditos
        </div>
        <div className="text-sm text-text-muted mt-1">
          = {balance?.balance?.toFixed(0) || 0} minutos de agente IA
        </div>
        {balance?.balance < 20 && balance?.balance > 0 && (
          <div className="mt-3 flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded px-3 py-2 text-sm text-yellow-400">
            <AlertTriangle size={16} />
            Tu balance es bajo. Recarga para no interrumpir el servicio.
          </div>
        )}
        {balance?.balance <= 0 && (
          <div className="mt-3 flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded px-3 py-2 text-sm text-red-400">
            <AlertTriangle size={16} />
            Sin créditos. Tu agente no podrá atender llamadas hasta que recargues.
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-green-500/10">
            <TrendingUp size={20} className="text-green-400" />
          </div>
          <div>
            <div className="text-xs text-text-muted">Total comprado</div>
            <div className="text-lg font-bold text-green-400">
              {balance?.total_purchased?.toFixed(0) || 0} min
            </div>
          </div>
        </Card>
        <Card className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-red-500/10">
            <TrendingDown size={20} className="text-red-400" />
          </div>
          <div>
            <div className="text-xs text-text-muted">Total consumido</div>
            <div className="text-lg font-bold text-red-400">
              {balance?.total_consumed?.toFixed(0) || 0} min
            </div>
          </div>
        </Card>
        <Card className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-500/10">
            <Gift size={20} className="text-purple-400" />
          </div>
          <div>
            <div className="text-xs text-text-muted">Créditos de regalo</div>
            <div className="text-lg font-bold text-purple-400">
              {balance?.total_gifted?.toFixed(0) || 0} min
            </div>
          </div>
        </Card>
      </div>

      {/* Paquetes de créditos */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Comprar créditos</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {packages.map(pkg => (
            <Card
              key={pkg.id}
              className={`relative ${
                pkg.is_popular ? 'ring-2 ring-accent border-accent' : ''
              }`}
            >
              {pkg.is_popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-bg-primary text-xs px-3 py-0.5 rounded-full font-medium">
                  Más popular
                </div>
              )}
              <h3 className="font-semibold text-lg">{pkg.name}</h3>
              <p className="text-xs text-text-muted mt-1">{pkg.description}</p>
              <div className="text-3xl font-bold mt-3">
                {pkg.credits?.toLocaleString()}
                <span className="text-sm font-normal text-text-muted"> min</span>
              </div>
              <div className="text-sm text-text-muted mt-1">
                ${pkg.price_per_credit_usd}/min
              </div>
              <div className="mt-3">
                <div className="text-xl font-semibold">${pkg.price_usd} USD</div>
                <div className="text-sm text-text-muted">${pkg.price_mxn} MXN</div>
              </div>
              {pkg.volume_discount > 0 && (
                <div className="text-xs text-green-400 mt-1">
                  {(pkg.volume_discount * 100).toFixed(0)}% descuento incluido
                </div>
              )}
              <div className="mt-4 space-y-2">
                <button
                  onClick={() => handlePurchase(pkg.id, 'stripe')}
                  disabled={purchasing !== null}
                  className="w-full bg-accent text-bg-primary rounded-lg py-2 text-sm font-medium hover:bg-accent/90 disabled:opacity-50 cursor-pointer transition-colors"
                >
                  {purchasing === pkg.id + 'stripe' ? 'Procesando...' : 'Pagar con tarjeta'}
                </button>
                <button
                  onClick={() => handlePurchase(pkg.id, 'mercadopago')}
                  disabled={purchasing !== null}
                  className="w-full bg-sky-500 text-white rounded-lg py-2 text-sm font-medium hover:bg-sky-600 disabled:opacity-50 cursor-pointer transition-colors"
                >
                  {purchasing === pkg.id + 'mercadopago' ? 'Procesando...' : 'Mercado Pago / OXXO'}
                </button>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Historial de transacciones */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Historial de transacciones</h2>
        {transactions.length === 0 ? (
          <div className="text-center text-text-muted py-8">
            No hay transacciones aún
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 px-3 font-medium text-text-muted">Fecha</th>
                  <th className="py-2 px-3 font-medium text-text-muted">Tipo</th>
                  <th className="py-2 px-3 font-medium text-text-muted text-right">Créditos</th>
                  <th className="py-2 px-3 font-medium text-text-muted text-right">Balance</th>
                  <th className="py-2 px-3 font-medium text-text-muted">Detalle</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(tx => (
                  <tr key={tx.id} className="border-b border-border/50 hover:bg-bg-hover transition-colors">
                    <td className="py-2 px-3 text-text-muted text-xs">
                      {formatDate(tx.created_at)}
                    </td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeBadgeClass(tx.type)}`}>
                        {typeLabel(tx.type)}
                      </span>
                    </td>
                    <td className={`py-2 px-3 text-right font-mono font-medium ${
                      tx.credits > 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {tx.credits > 0 ? '+' : ''}{tx.credits}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-text-muted">
                      {tx.balance_after}
                    </td>
                    <td className="py-2 px-3 text-text-muted text-xs">
                      {txDetail(tx)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
