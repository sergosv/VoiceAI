import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X } from 'lucide-react'
import { api } from '../lib/api'

const WARN_THRESHOLD = 20
const CRITICAL_THRESHOLD = 5
const POLL_INTERVAL = 5 * 60 * 1000 // 5 minutos

export function LowBalanceAlert() {
  const navigate = useNavigate()
  const [balance, setBalance] = useState(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer = null

    async function fetchBalance() {
      try {
        const data = await api.get('/billing/balance')
        if (!cancelled) setBalance(data?.balance ?? null)
      } catch {
        // Silencioso — no bloquear UX por error de balance
      }
    }

    fetchBalance()
    timer = setInterval(fetchBalance, POLL_INTERVAL)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  // No mostrar si no hay datos, balance suficiente, o fue cerrado
  if (balance === null || balance >= WARN_THRESHOLD || dismissed) return null

  const isCritical = balance < CRITICAL_THRESHOLD

  return (
    <div
      className={`flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg text-sm ${
        isCritical
          ? 'bg-red-500/10 border border-red-500/30 text-red-300'
          : 'bg-yellow-500/10 border border-yellow-500/30 text-yellow-300'
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle size={16} className="shrink-0" />
        <span className="truncate">
          {isCritical
            ? `Balance critico (${balance.toFixed(1)} creditos). Tus agentes se detendran pronto.`
            : `Tu balance es bajo (${balance.toFixed(1)} creditos). Compra mas para evitar interrupciones.`}
        </span>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => navigate('/billing')}
          className={`px-3 py-1 rounded text-xs font-semibold transition-colors cursor-pointer ${
            isCritical
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-yellow-500 hover:bg-yellow-600 text-black'
          }`}
        >
          Comprar creditos
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="p-0.5 rounded hover:bg-white/10 transition-colors cursor-pointer"
          aria-label="Cerrar alerta"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
