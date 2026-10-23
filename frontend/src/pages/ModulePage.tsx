import type { PlatformModule } from '../features/modules'

export function ModulePage({ module }: { module: PlatformModule }) {
  return (
    <>
      <span className="eyebrow">{module.stories}</span>
      <h1>{module.label}</h1>
      <div className="panel">
        <h2>Módulo preparado</h2>
        <p>{module.description}</p>
        <p>Las funcionalidades de este módulo se incorporarán durante los próximos sprints.</p>
      </div>
    </>
  )
}
