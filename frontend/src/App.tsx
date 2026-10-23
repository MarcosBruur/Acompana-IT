import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import { modules } from './features/modules'
import { Dashboard } from './pages/Dashboard'
import { ModulePage } from './pages/ModulePage'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <aside className="sidebar">
          <Link className="brand" to="/">Acompañamiento <span>IT</span></Link>
          <p className="sidebar-caption">Tu camino hacia el primer empleo tecnológico</p>
          <nav aria-label="Navegación principal">
            <NavLink to="/" end>Inicio</NavLink>
            {modules.map((module) => (
              <NavLink key={module.path} to={module.path}>{module.label}</NavLink>
            ))}
          </nav>
        </aside>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            {modules.map((module) => (
              <Route key={module.path} path={module.path} element={<ModulePage module={module} />} />
            ))}
            <Route path="*" element={<section><h1>Página no encontrada</h1><Link to="/">Volver al inicio</Link></section>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
