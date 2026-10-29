import { useRef, useState } from 'react'
import { Asset, Header } from '../components/Design'

export function ResumePage() {
  const input = useRef<HTMLInputElement>(null)
  const [selected, setSelected] = useState<{
    name: string
    date: string
  } | null>(null)
  const [message, setMessage] = useState('')
  const [dragging, setDragging] = useState(false)
  async function select(file?: File) {
    if (!file) return
    if (
      !file.name.toLowerCase().endsWith('.pdf') ||
      file.type !== 'application/pdf' ||
      file.size > 5 * 1024 * 1024
    ) {
      setMessage('Seleccioná un PDF de hasta 5 MB.')
      return
    }
    try {
      if ((await file.slice(0, 5).text()) !== '%PDF-') {
        setMessage('El archivo no tiene una cabecera PDF válida.')
        return
      }
      setSelected({
        name: file.name,
        date: new Intl.DateTimeFormat('es-AR', { dateStyle: 'long' }).format(
          new Date(),
        ),
      })
      setMessage(
        'PDF seleccionado para vista previa local. El archivo no se subió ni se guardó; la carga al servidor está pendiente.',
      )
    } catch {
      setMessage('No se pudo leer el archivo. Volvé a seleccionarlo.')
    }
  }
  return (
    <>
      <Header title="Mi currículum" screen="resume" />
      <div className="resume-content">
        <p className="intro">
          Tu CV se utilizará para comparar tu perfil con las oportunidades
          laborales y evaluar tu compatibilidad.
        </p>
        <section className="panel upload-panel">
          <h2>Cargá tu currículum</h2>
          <div
            className={`dropzone ${dragging ? 'dragging' : ''}`}
            onDragOver={(event) => {
              event.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              void select(event.dataTransfer.files[0])
            }}
          >
            <Asset screen="resume" name="imgUploadIcon" />
            <h3>Arrastrá y soltá tu CV aquí</h3>
            <p>Formato PDF · Máximo 5 MB</p>
            <button className="primary" onClick={() => input.current?.click()}>
              Seleccionar PDF
            </button>
            <input
              ref={input}
              className="visually-hidden"
              type="file"
              accept=".pdf,application/pdf"
              aria-label="Seleccionar currículum PDF"
              onChange={(event) => {
                void select(event.target.files?.[0])
                event.target.value = ''
              }}
            />
          </div>
        </section>
        <section className="panel current-cv">
          <div className="cv-heading">
            <h2>Currículum actual</h2>
            <span className="pill green">
              {selected ? 'Selección local' : 'CV de ejemplo'}
            </span>
          </div>
          <div className="file-details">
            <div className="pdf-badge">
              <Asset screen="resume" name="imgFile1" />
              <span>PDF</span>
            </div>
            <div className="file-meta">
              <strong>{selected?.name ?? 'Marcos_CV.pdf'}</strong>
              <p>
                {selected ? 'Fecha de selección: ' : 'Fecha de carga: '}
                {selected?.date ?? '27 de septiembre de 2026'}
              </p>
            </div>
            <button
              className="secondary"
              onClick={() => input.current?.click()}
            >
              Reemplazar CV
            </button>
          </div>
        </section>
        <p className="helper">
          Al cargar un nuevo archivo, se reemplazará el CV actual.
        </p>
        {message && (
          <p className="inline-notice" role="status">
            {message}
          </p>
        )}
      </div>
    </>
  )
}
