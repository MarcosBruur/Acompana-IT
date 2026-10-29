import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Asset, Modal, PreviewNotice } from '../components/Design'

export function AuthPage({ register = false }: { register?: boolean }) {
  const screen = register ? 'registration' : 'login'
  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const [message, setMessage] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    if (register && form.get('password') !== form.get('confirm')) {
      setMessage('Las contraseñas deben coincidir.')
      return
    }
    setMessage(
      register
        ? 'El formulario es válido. El registro de cuentas estará disponible cuando se implemente la autenticación.'
        : 'El inicio de sesión estará disponible cuando se implemente la autenticación. Podés recorrer las pantallas desde «Explorar maqueta».',
    )
  }
  function field(
    name: string,
    label: string,
    placeholder: string,
    password = false,
  ) {
    return (
      <div className="field" key={name}>
        <span className="field-label">
          <label htmlFor={`auth-${name}`}>{label}</label>
          {name === 'password' && !register && (
            <button
              type="button"
              className="text-button forgot"
              onClick={() =>
                setMessage(
                  'La recuperación de contraseña está pendiente de implementación.',
                )
              }
            >
              ¿Olvidé mi contraseña?
            </button>
          )}
        </span>
        <span className="input-wrapper">
          <Asset
            screen={screen}
            name={password ? 'imgLockKeyhole' : 'imgUser'}
          />
          <input
            id={`auth-${name}`}
            name={name}
            type={
              password && !visible[name]
                ? 'password'
                : name === 'email'
                  ? 'email'
                  : 'text'
            }
            placeholder={placeholder}
            required
            autoComplete={
              name === 'email'
                ? 'email'
                : password
                  ? register
                    ? 'new-password'
                    : 'current-password'
                  : name === 'name'
                    ? 'given-name'
                    : 'family-name'
            }
            minLength={password && register ? 8 : undefined}
            pattern={
              password && register
                ? '(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,}'
                : undefined
            }
            title={
              password && register
                ? 'Mínimo 8 caracteres, una mayúscula, un número y un carácter especial.'
                : undefined
            }
          />
          {password && (
            <button
              type="button"
              className="icon-button"
              aria-label={`${visible[name] ? 'Ocultar' : 'Mostrar'} ${label.toLowerCase()}`}
              aria-pressed={Boolean(visible[name])}
              onClick={() =>
                setVisible((current) => ({
                  ...current,
                  [name]: !current[name],
                }))
              }
            >
              <Asset screen={screen} name="imgEye" />
            </button>
          )}
        </span>
      </div>
    )
  }
  return (
    <>
      <div className={`auth-layout ${register ? 'registration' : ''}`}>
        <section
          className="brand-panel"
          aria-label="Presentación de la plataforma"
        >
          <Asset screen={screen} name="imgGlowOrbTeal" className="brand-teal" />
          <Asset screen={screen} name="imgGlowOrbBlue" className="brand-blue" />
          <Asset screen={screen} name="imgNodeMesh" className="brand-mesh" />
          <div className="brand-copy">
            <h1>Tu carrera en tecnología comienza aquí</h1>
            <p>
              Te acompañamos de inicio a fin. Prepárate para el mercado real con
              simulacros de entrevista, orientación técnica, consejos prácticos
              y recursos de aprendizaje.
            </p>
          </div>
        </section>
        <main className="auth-panel">
          <form className="auth-form" onSubmit={submit}>
            <header>
              <h2>{register ? 'Crear cuenta' : 'Iniciar sesión'}</h2>
              <p>
                {register
                  ? 'Comienza tu preparación uniéndote a la plataforma'
                  : 'Ingresa tus credenciales para unirte a la plataforma'}
              </p>
            </header>
            <div className="fields-stack">
              {register && (
                <div className="name-row">
                  {field('name', 'Nombre/s', 'Tu nombre')}
                  {field('surname', 'Apellido/s', 'Tu apellido/s')}
                </div>
              )}
              {field('email', 'Correo electrónico', 'correo@ejemplo.com')}
              {field(
                'password',
                'Contraseña',
                register ? 'Crear contraseña' : '••••••••',
                true,
              )}
              {register && (
                <>
                  {field(
                    'confirm',
                    'Confirmar contraseña',
                    'Confirmar contraseña',
                    true,
                  )}
                  <small className="password-hint">
                    Mínimo 8 caracteres, mayúscula, número y carácter especial.
                  </small>
                </>
              )}
            </div>
            {register && (
              <label className="terms">
                <input type="checkbox" required defaultChecked />
                <span className="checkbox-art">
                  <Asset screen="registration" name="imgCheck" />
                </span>
                <span>
                  Acepto los{' '}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      setMessage(
                        'Los términos de servicio estarán disponibles antes de habilitar el registro.',
                      )
                    }
                  >
                    Términos de servicio
                  </button>{' '}
                  y la{' '}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      setMessage(
                        'La política de privacidad estará disponible antes de habilitar el registro.',
                      )
                    }
                  >
                    Política de privacidad
                  </button>
                </span>
              </label>
            )}
            <div className="auth-actions">
              <button className="primary" type="submit">
                {register ? 'Registrarse' : 'Ingresar a la plataforma'}
              </button>
              {!register && (
                <>
                  <div className="oauth-divider">
                    <Asset screen="login" name="imgLeftLine" />
                    <span>O ACCEDE CON</span>
                    <Asset screen="login" name="imgLeftLine" />
                  </div>
                  <button
                    className="google-button"
                    type="button"
                    onClick={() =>
                      setMessage(
                        'El acceso con Google requiere configurar OAuth y todavía no está disponible.',
                      )
                    }
                  >
                    Continuar con Google
                  </button>
                </>
              )}
            </div>
            <p className="auth-footer">
              {register ? '¿Ya tienes cuenta?' : '¿No tienes una cuenta aún?'}{' '}
              <Link to={register ? '/sesion' : '/registro'}>
                {register ? 'Iniciar sesión' : 'Crear cuenta'}
              </Link>
            </p>
            <Link className="explore-link" to="/">
              Explorar maqueta
            </Link>
          </form>
        </main>
      </div>
      <PreviewNotice />
      {message && (
        <Modal title="Vista previa" onClose={() => setMessage('')}>
          <p role="status">{message}</p>
        </Modal>
      )}
    </>
  )
}
