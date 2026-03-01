import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { ConfirmProvider } from './context/ConfirmContext'
import { DashboardLayout } from './layouts/DashboardLayout'
import { AuthLayout } from './layouts/AuthLayout'
import { AdminRoute } from './components/AdminRoute'
import { PageLoader } from './components/ui/Spinner'

// Lazy-load pages for code-splitting
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ForgotPassword })))
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })))
const Calls = lazy(() => import('./pages/Calls').then(m => ({ default: m.Calls })))
const CallDetail = lazy(() => import('./pages/CallDetail').then(m => ({ default: m.CallDetail })))
const Documents = lazy(() => import('./pages/Documents').then(m => ({ default: m.Documents })))
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })))
const ClientsList = lazy(() => import('./pages/admin/ClientsList').then(m => ({ default: m.ClientsList })))
const ClientDetail = lazy(() => import('./pages/admin/ClientDetail').then(m => ({ default: m.ClientDetail })))
const ClientCreate = lazy(() => import('./pages/admin/ClientCreate').then(m => ({ default: m.ClientCreate })))
const Contacts = lazy(() => import('./pages/Contacts').then(m => ({ default: m.Contacts })))
const ContactDetail = lazy(() => import('./pages/ContactDetail').then(m => ({ default: m.ContactDetail })))
const Appointments = lazy(() => import('./pages/Appointments').then(m => ({ default: m.Appointments })))
const Campaigns = lazy(() => import('./pages/Campaigns').then(m => ({ default: m.Campaigns })))
const CampaignDetail = lazy(() => import('./pages/CampaignDetail').then(m => ({ default: m.CampaignDetail })))
const Integrations = lazy(() => import('./pages/Integrations').then(m => ({ default: m.Integrations })))
const AgentDetail = lazy(() => import('./pages/AgentDetail').then(m => ({ default: m.AgentDetail })))
const NotFound = lazy(() => import('./pages/NotFound').then(m => ({ default: m.NotFound })))

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
        <ConfirmProvider>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Auth */}
              <Route element={<AuthLayout />}>
                <Route path="/login" element={<Login />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
              </Route>

              {/* Dashboard */}
              <Route element={<DashboardLayout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/calls" element={<Calls />} />
                <Route path="/calls/:id" element={<CallDetail />} />
                <Route path="/contacts" element={<Contacts />} />
                <Route path="/contacts/:id" element={<ContactDetail />} />
                <Route path="/appointments" element={<Appointments />} />
                <Route path="/campaigns" element={<Campaigns />} />
                <Route path="/campaigns/:id" element={<CampaignDetail />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/integrations" element={<Integrations />} />
                <Route path="/agents/:agentId" element={<AgentDetail />} />
                <Route path="/settings" element={<Settings />} />

                {/* Admin — protegido */}
                <Route path="/admin/clients" element={<AdminRoute><ClientsList /></AdminRoute>} />
                <Route path="/admin/clients/new" element={<AdminRoute><ClientCreate /></AdminRoute>} />
                <Route path="/admin/clients/:id" element={<AdminRoute><ClientDetail /></AdminRoute>} />
              </Route>

              {/* 404 */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ConfirmProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
