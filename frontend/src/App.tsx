import {
  BrowserRouter,
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { modules } from './features/modules'
import { Asset, PreviewNotice, type DesignScreen } from './components/Design'
import { Dashboard } from './pages/Dashboard'
import { AuthPage } from './pages/AuthPage'
import { ResumePage } from './pages/ResumePage'
import { VacancyPage, AnalysisPage } from './pages/VacancyPage'
import { InterviewPage } from './pages/InterviewPage'
import { ModulePage } from './pages/ModulePage'
import './App.css'

function Layout() {
  const { pathname } = useLocation()
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
        <Link className="logout" to="/sesion">
          <Asset screen={screen} name="imgLogOut" />
          Cerrar sesión
        </Link>
      </aside>
      <main id="contenido" className="content">
        <Outlet />
        <PreviewNotice />
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/sesion" element={<AuthPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/registro" element={<AuthPage register />} />
        <Route path="/register" element={<AuthPage register />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="/curriculum" element={<ResumePage />} />
          <Route path="/vacantes" element={<VacancyPage />} />
          <Route path="/vacantes/nueva" element={<VacancyPage />} />
          <Route path="/vacantes/ejemplo/analisis" element={<AnalysisPage />} />
          <Route path="/entrevistas" element={<InterviewPage />} />
          {modules
            .filter((module) =>
              ['/comparaciones', '/aprendizaje'].includes(module.path),
            )
            .map((module) => (
              <Route
                key={module.path}
                path={module.path}
                element={<ModulePage module={module} />}
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
      </Routes>
    </BrowserRouter>
  )
}

export default App
