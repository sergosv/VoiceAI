import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '../components/ui/Button'

export function NotFound() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center">
      <div className="text-center">
        <p className="text-6xl font-bold text-accent/30 font-mono">404</p>
        <p className="text-text-secondary mt-2 mb-6">Página no encontrada</p>
        <Button onClick={() => navigate('/')}>
          <ArrowLeft size={16} className="mr-2 inline" /> Volver al dashboard
        </Button>
      </div>
    </div>
  )
}
