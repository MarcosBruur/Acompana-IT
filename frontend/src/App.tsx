import {
  BrowserRouter,
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  Navigate,
  useNavigate,
} from 'react-router-dom'
import { AuthProvider } from './features/auth'
import { NotificationsProvider } from './features/notifications'
import { useNotifications } from './features/notifications-context'
import { useAuth } from './features/auth-context'
import { useGuestAccessLink } from './features/guest-access'
import { modules } from './features/modules'
import { Asset, Modal, type DesignScreen } from './components/Design'
import { Dashboard } from './pages/Dashboard'
import { AuthPage } from './pages/AuthPage'
import { VacancyPage, NewVacancyPage, AnalysisPage } from './pages/VacancyPage'
import { InterviewSetupPage, InterviewSessionPage } from './pages/InterviewPage'
import { InterviewHistoryPage, InterviewResultPage } from './pages/InterviewHistoryPage'
import { ModulePage } from './pages/ModulePage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ProfilePage } from './pages/ProfilePage'
import logo from './assets/logo.png'
import './App.css'
import './theme.css'

function Layout() {
  const location = useLocation()
  const { pathname } = location
  const navigate = useNavigate()
  const { candidate, logout } = useAuth()
  const notifications = useNotifications()
  const onProfileClick = useGuestAccessLink('profile')
  const onInterviewClick = useGuestAccessLink('interviews')
  const requestedPrompt = (location.state as { accessPrompt?: string } | null)?.accessPrompt
  const prompt = !candidate && (requestedPrompt === 'profile' || requestedPrompt === 'interviews') ? requestedPrompt : null
  function closePrompt() {
    const state = { ...(location.state ?? {}) }
    delete state.accessPrompt
    navigate(`${pathname}${location.search}${location.hash}`, { replace: true, state })
  }
  const screen: DesignScreen =
    pathname.includes('/analisis')
        ? 'analysis'
        : pathname.startsWith('/vacantes')
          ? 'vacancy'
           : pathname.startsWith('/entrevistas')
            ? 'interview'
            : 'dashboard'
  return (
    <div className="layout">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <aside className="sidebar">
        <Link className="sidebar-brand" to="/" aria-label="CHOOMIT, ir al inicio">
          <img className="brand-logo" src={logo} alt="" />
        </Link>
        <nav aria-label="Navegación principal">
          {[
            { to: '/', label: 'Inicio', icon: 'imgGrid' },
            { to: '/perfil', label: 'Perfil', icon: 'imgAvatar' },
            { to: '/vacantes', label: 'Mis vacantes', icon: 'imgBriefcase' },
            {
              to: '/entrevistas',
              label: 'Simular Entrevista',
              icon: 'imgMessageCircle',
            },
          ].map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} onClick={item.to === '/perfil' ? onProfileClick : item.to === '/entrevistas' ? onInterviewClick : undefined}>
              <Asset screen={screen} name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        {candidate ? (
          <button className="logout" type="button" onClick={() => {
              void logout().then(() => { notifications.success('Sesión cerrada correctamente.'); navigate('/sesion') }).catch(() => notifications.error('No se pudo cambiar de cuenta. Intentá de nuevo.'))
           }}>
             <Asset screen={screen} name="imgLogOut" />Cambiar cuenta
          </button>
        ) : (
          <Link className="logout" to="/sesion"><Asset screen={screen} name="imgLogOut" />Iniciar sesión</Link>
        )}
      </aside>
      <main id="contenido" className="content">
        <Outlet />
      </main>
      {prompt && <Modal title={prompt === 'profile' ? 'Accedé a tu perfil' : 'Accedé a las entrevistas'} onClose={closePrompt}>
        <p>{prompt === 'profile' ? 'Para consultar y editar tu perfil, primero necesitás una cuenta.' : 'Para practicar entrevistas y consultar tus resultados, primero necesitás una cuenta.'} ¿Cómo querés continuar?</p>
        <div className="profile-access-actions">
          <Link className="primary" to="/registro" state={{ from: prompt === 'profile' ? '/perfil' : '/entrevistas' }}>Crear cuenta</Link>
          <Link className="secondary" to="/sesion" state={{ from: prompt === 'profile' ? '/perfil' : '/entrevistas' }}>Iniciar sesión</Link>
        </div>
      </Modal>}
    </div>
  )
}

function RequireAccount({ children, promptForInterview = false }: { children: React.ReactNode; promptForInterview?: boolean }) {
  const { candidate, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p role="status">Cargando sesión…</p>
  if (!candidate) return promptForInterview
    ? <Navigate to="/" state={{ accessPrompt: 'interviews' }} replace />
    : <Navigate to="/sesion" state={{ from: location.pathname }} replace />
  if (candidate.password_expired) return <Navigate to="/cambiar-contrasena" state={{ from: location.pathname }} replace />
  return children
}

function ProfileAccess() {
  const { candidate, loading } = useAuth()
  if (loading) return <p role="status">Cargando sesión…</p>
  if (candidate?.password_expired) return <Navigate to="/cambiar-contrasena" state={{ from: '/perfil' }} replace />
  if (candidate) return <ProfilePage />
  return <Navigate to="/" state={{ accessPrompt: 'profile' }} replace />
}

function RequireRenewal() {
  const { candidate, loading } = useAuth()
  if (loading) return <p role="status">Cargando sesión…</p>
  if (!candidate) return <Navigate to="/sesion" replace />
  return <ChangePasswordPage />
}

function App() {
  return (
    <BrowserRouter>
      <NotificationsProvider><AuthProvider><Routes>
        <Route path="/sesion" element={<AuthPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/registro" element={<AuthPage register />} />
        <Route path="/register" element={<AuthPage register />} />
        <Route path="/cambiar-contrasena" element={<RequireRenewal />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="/curriculum" element={<Navigate to="/perfil" replace />} />
           <Route path="/perfil" element={<ProfileAccess />} />
          <Route path="/vacantes" element={<VacancyPage />} />
          <Route path="/vacantes/nueva" element={<NewVacancyPage />} />
          <Route path="/vacantes/analisis" element={<AnalysisPage />} />
          <Route path="/vacantes/:id/analisis" element={<AnalysisPage />} />
           <Route path="/entrevistas" element={<RequireAccount promptForInterview><InterviewHistoryPage /></RequireAccount>} />
            <Route path="/entrevistas/nueva" element={<RequireAccount promptForInterview><InterviewSetupPage /></RequireAccount>} />
            <Route path="/entrevistas/:id/simulacion" element={<RequireAccount promptForInterview><InterviewSessionPage /></RequireAccount>} />
           <Route path="/entrevistas/:id" element={<RequireAccount promptForInterview><InterviewResultPage /></RequireAccount>} />
          {modules.map((module) => (
              <Route
                key={module.path}
                path={module.path}
                element={module.path === '/comparaciones' ? <RequireAccount><ModulePage module={module} /></RequireAccount> : <ModulePage module={module} />}
              />
            ))}
          <Route
            path="*"
            element={
              <section>
                <h1>Página no encontrada</h1>
                <Link to="/">Volver al inicio</Link>
              </section>
            }
          />
        </Route>
      </Routes></AuthProvider></NotificationsProvider>
    </BrowserRouter>
  )
}

export default App
