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
import { useAuth } from './features/auth-context'
import { modules } from './features/modules'
import { Asset, PreviewNotice, type DesignScreen } from './components/Design'
import { Dashboard } from './pages/Dashboard'
import { AuthPage } from './pages/AuthPage'
import { ResumePage } from './pages/ResumePage'
import { VacancyPage, AnalysisPage } from './pages/VacancyPage'
import { InterviewPage } from './pages/InterviewPage'
import { ModulePage } from './pages/ModulePage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import './App.css'

function Layout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { candidate, logout } = useAuth()
  const screen: DesignScreen =
    pathname === '/curriculum'
      ? 'resume'
      : pathname.includes('/analisis')
        ? 'analysis'
        : pathname.startsWith('/vacantes')
          ? 'vacancy'
          : pathname === '/entrevistas'
            ? 'interview'
            : 'dashboard'
  return (
    <div className="layout">
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <aside className="sidebar">
        <Asset screen={screen} name="imgGlow" className="sidebar-glow" />
        <nav aria-label="Navegación principal">
          {[
            { to: '/', label: 'Inicio', icon: 'imgGrid' },
            { to: '/curriculum', label: 'Mi currículum', icon: 'imgFile' },
            { to: '/vacantes', label: 'Mis vacantes', icon: 'imgBriefcase' },
            {
              to: '/entrevistas',
              label: 'Simular Entrevista',
              icon: 'imgMessageCircle',
            },
          ].map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'}>
              <Asset screen={screen} name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        {candidate ? (
          <button className="logout" type="button" onClick={() => {
            void logout().then(() => navigate('/')).catch(() => window.alert('No se pudo cerrar la sesión. Intentá de nuevo.'))
          }}>
            <Asset screen={screen} name="imgLogOut" />Cerrar sesión
          </button>
        ) : (
          <Link className="logout" to="/sesion"><Asset screen={screen} name="imgLogOut" />Iniciar sesión</Link>
        )}
      </aside>
      <main id="contenido" className="content">
        <Outlet />
        <PreviewNotice />
      </main>
    </div>
  )
}

function RequireAccount({ children }: { children: React.ReactNode }) {
  const { candidate, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p role="status">Cargando sesión…</p>
  if (!candidate) return <Navigate to="/sesion" state={{ from: location.pathname }} replace />
  if (candidate.password_expired) return <Navigate to="/cambiar-contrasena" state={{ from: location.pathname }} replace />
  return children
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
      <AuthProvider><Routes>
        <Route path="/sesion" element={<AuthPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/registro" element={<AuthPage register />} />
        <Route path="/register" element={<AuthPage register />} />
        <Route path="/cambiar-contrasena" element={<RequireRenewal />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="/curriculum" element={<ResumePage />} />
          <Route path="/vacantes" element={<VacancyPage />} />
          <Route path="/vacantes/nueva" element={<VacancyPage />} />
          <Route path="/vacantes/ejemplo/analisis" element={<AnalysisPage />} />
          <Route path="/entrevistas" element={<RequireAccount><InterviewPage /></RequireAccount>} />
          {modules
            .filter((module) =>
              ['/comparaciones', '/aprendizaje'].includes(module.path),
            )
            .map((module) => (
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
      </Routes></AuthProvider>
    </BrowserRouter>
  )
}

export default App
