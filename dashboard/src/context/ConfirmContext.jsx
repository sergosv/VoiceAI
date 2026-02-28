import { createContext, useContext, useState, useCallback } from 'react'
import { AlertTriangle, Trash2, HelpCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'

const ConfirmContext = createContext(null)

const icons = {
  danger: <Trash2 size={24} className="text-danger" />,
  warning: <AlertTriangle size={24} className="text-warning" />,
  info: <HelpCircle size={24} className="text-accent" />,
}

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null)

  const confirm = useCallback(({ title, message, confirmText = 'Confirmar', variant = 'danger' }) => {
    return new Promise(resolve => {
      setState({ title, message, confirmText, variant, resolve })
    })
  }, [])

  function handleConfirm() {
    state?.resolve(true)
    setState(null)
  }

  function handleCancel() {
    state?.resolve(false)
    setState(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {state && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleCancel} />
          <div className="relative bg-bg-secondary border border-border rounded-xl p-6 max-w-sm w-full mx-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-full bg-bg-primary flex items-center justify-center mb-4">
                {icons[state.variant] || icons.info}
              </div>
              <h3 className="text-lg font-semibold mb-2">{state.title}</h3>
              <p className="text-sm text-text-muted mb-6">{state.message}</p>
              <div className="flex gap-3 w-full">
                <Button variant="secondary" onClick={handleCancel} className="flex-1">
                  Cancelar
                </Button>
                <Button
                  variant={state.variant === 'danger' ? 'danger' : 'primary'}
                  onClick={handleConfirm}
                  className="flex-1"
                >
                  {state.confirmText}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm debe usarse dentro de ConfirmProvider')
  return ctx
}
