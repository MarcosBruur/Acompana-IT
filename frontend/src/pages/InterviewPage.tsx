import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Asset, Header, Modal } from '../components/Design'

export function InterviewPage() {
  const [muted, setMuted] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [ended, setEnded] = useState(false)
  return (
    <>
      <Header title="Simulación de entrevista técnica" screen="interview" />
      <div className="interview-session">
        <div className="selected-vacancy">
          <p>Vacante seleccionada</p>
          <strong>Desarrollador/a Frontend React</strong>
        </div>
        {ended ? (
          <section className="panel">
            <h2>Vista previa finalizada</h2>
            <p>
              Esta maqueta no graba audio ni genera puntuación o feedback. La
              entrevista con IA está pendiente de integración.
            </p>
            <button
              className="primary"
              onClick={() => {
                setEnded(false)
                setMuted(false)
              }}
            >
              Volver a la simulación de ejemplo
            </button>
            <Link className="example-link" to="/">
              Volver al inicio
            </Link>
          </section>
        ) : (
          <div className="voice-interview">
            <div className="interview-progress">
              <span>Pregunta 3 de 10</span>
              <div
                className="progress-track"
                role="progressbar"
                aria-label="Progreso de la entrevista de ejemplo"
                aria-valuenow={3}
                aria-valuemin={0}
                aria-valuemax={10}
              >
                <div />
              </div>
            </div>
            <div className="voice-conversation">
              <div className="voice-orb">
                <Asset
                  screen="interview"
                  name="imgSoftCyanHalo"
                  className="orb-halo"
                />
                <Asset
                  screen="interview"
                  name="imgVoiceOrbBlueCyan"
                  className="orb-color"
                />
                <div className="voice-waveform">
                  {[14, 28, 42, 26, 16].map((height, i) => (
                    <span key={i} style={{ height }} />
                  ))}
                </div>
              </div>
              <h2>{muted ? 'Micrófono silenciado' : 'Te estoy escuchando'}</h2>
            </div>
            <div className="current-question">
              <p>PREGUNTA ACTUAL · REACT</p>
              <h2>
                ¿Cuál es la diferencia entre useState y useEffect,
                <br /> y en qué situaciones usarías cada uno?
              </h2>
            </div>
            <div className="voice-controls">
              <button
                className="voice-control"
                aria-pressed={muted}
                onClick={() => setMuted(!muted)}
              >
                <Asset screen="interview" name="imgMicrophoneButton" />
                <span>
                  {muted ? 'Activar micrófono' : 'Silenciar micrófono'}
                </span>
              </button>
              <button
                className="voice-control"
                onClick={() => setConfirm(true)}
              >
                <Asset screen="interview" name="imgEndInterviewButton" />
                <span>Finalizar entrevista</span>
              </button>
            </div>
            <p className="voice-note" role="status">
              Simulación visual · El micrófono no está conectado y no se graba
              audio.
            </p>
          </div>
        )}
      </div>
      {confirm && (
        <Modal title="¿Finalizar entrevista?" onClose={() => setConfirm(false)}>
          <p>
            Vas a finalizar esta vista previa. La generación de puntuación y
            feedback todavía no está disponible.
          </p>
          <button
            className="primary"
            onClick={() => {
              setConfirm(false)
              setEnded(true)
            }}
          >
            Confirmar finalización
          </button>
        </Modal>
      )}
    </>
  )
}
