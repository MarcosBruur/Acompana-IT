import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Asset } from '../components/Design'
import { FieldError } from '../components/FieldError'
import { useAuth } from '../features/auth-context'
import { required, validateConfirmation, validateEmail, validatePassword } from '../features/auth-validation'
import { AuthRequestError, authRequest, googleLoginUrl, type Candidate } from '../services/auth'

type FieldName = 'name' | 'surname' | 'email' | 'password' | 'confirm'
type Values = Record<FieldName, string>
type Errors = Partial<Record<FieldName, string>>
const initialValues: Values = { name: '', surname: '', email: '', password: '', confirm: '' }

function validateField(name: FieldName, values: Values, register: boolean): string | undefined {
  const value = values[name]
  if (name === 'email') return validateEmail(value)
  if (name === 'password') return register ? validatePassword(value) : required(value)
  if (name === 'confirm') return validateConfirmation(value, values.password)
  if (required(value)) return required(value)
  if (value.trim().length > 100) return 'Ingresá hasta 100 caracteres.'
}

export function AuthPage({ register = false }: { register?: boolean }) {
  const screen = register ? 'registration' : 'login'
  const [visible, setVisible] = useState<Record<string, boolean>>({})
  const [values, setValues] = useState<Values>(initialValues)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [googleAvailable, setGoogleAvailable] = useState(false)
  const { candidate, loading, setCandidate } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const destination = (location.state as { from?: string } | null)?.from ?? '/'
  const googleError = params.get('google_error')

  function updateField(name: FieldName, value: string) {
    if (name === 'email' && googleError === 'linked') {
      setParams((current) => {
        const next = new URLSearchParams(current)
        next.delete('google_error')
        return next
      }, { replace: true })
    }
    const next = { ...values, [name]: value }
    setValues(next)
    setFormError('')
    setErrors((current) => ({
      ...current,
      [name]: current[name] ? validateField(name, next, register) : undefined,
      ...(name === 'password' && (next.confirm || current.confirm)
        ? { confirm: validateField('confirm', next, register) }
        : {}),
    }))
  }

  useEffect(() => {
    if (params.has('google_error')) sessionStorage.removeItem('auth_return_to')
    authRequest<{ available: boolean }>('/google/available')
      .then(({ available }) => setGoogleAvailable(available))
      .catch(() => setGoogleAvailable(false))
  }, [params])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields: FieldName[] = register
      ? ['name', 'surname', 'email', 'password', 'confirm']
      : ['email', 'password']
    const nextErrors: Errors = {}
    for (const name of fields) nextErrors[name] = validateField(name, values, register)
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return
    setBusy(true)
    setFormError('')
    try {
      const result = await authRequest<Candidate>(register ? '/register' : '/login', {
        method: 'POST',
        body: JSON.stringify(register ? {
          first_name: values.name.trim(), last_name: values.surname.trim(),
          email: values.email.trim(), password: values.password,
          confirm_password: values.confirm,
        } : { email: values.email.trim(), password: values.password }),
      })
      setCandidate(result)
      sessionStorage.removeItem('auth_return_to')
      navigate(result.password_expired ? '/cambiar-contrasena' : destination, { replace: true, state: { from: destination } })
    } catch (error) {
      if (error instanceof AuthRequestError) {
        const serverFields: Errors = {}
        const names: Record<string, FieldName> = {
          first_name: 'name', last_name: 'surname', email: 'email',
          password: 'password', confirm_password: 'confirm',
        }
        for (const [field, message] of Object.entries(error.fieldErrors)) {
          if (names[field]) serverFields[names[field]] = message
        }
        if (error.status === 409) serverFields.email = error.message
        if (error.status === 401) serverFields.password = error.message
        setErrors(serverFields)
        if (!Object.values(serverFields).some(Boolean)) setFormError(error.message)
      } else {
        setFormError('No se pudo conectar. Intentá de nuevo.')
      }
    } finally {
      setBusy(false)
    }
  }
  function field(
    name: FieldName,
    label: string,
    placeholder: string,
    password = false,
  ) {
    const error = errors[name] || (name === 'email' && googleError === 'linked'
      ? 'Este correo ya tiene una cuenta. Iniciá sesión con tu contraseña.' : undefined)
    const errorId = `auth-${name}-error`
    return (
      <div className="field" key={name}>
        <span className="field-label">
          <label htmlFor={`auth-${name}`}>{label}</label>
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
            value={values[name]}
            onChange={(event) => updateField(name, event.target.value)}
            onBlur={() => setErrors((current) => ({ ...current, [name]: validateField(name, values, register) }))}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
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
        <FieldError id={errorId} message={error} />
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
          <form className="auth-form" onSubmit={submit} noValidate>
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
            <div className="auth-actions">
              <button className="primary" type="submit" disabled={busy || loading}>
                {busy || loading ? 'Procesando…' : register ? 'Registrarse' : 'Ingresar a la plataforma'}
              </button>
              <FieldError id="auth-form-error" message={formError} />
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
                    disabled={!googleAvailable || busy || loading}
                    onClick={() => {
                      if (destination === '/comparaciones' || destination === '/entrevistas') sessionStorage.setItem('auth_return_to', destination)
                      window.location.assign(googleLoginUrl())
                    }}
                  >
                    Continuar con Google
                  </button>
                  {!googleAvailable && <small>El acceso con Google estará disponible cuando se configuren las credenciales OAuth.</small>}
                  <FieldError id="google-login-error" message={googleError && googleError !== 'linked' ? 'No se pudo iniciar sesión con Google. Intentá de nuevo.' : undefined} />
                </>
              )}
            </div>
            <p className="auth-footer">
              {register ? '¿Ya tienes cuenta?' : '¿No tienes una cuenta aún?'}{' '}
              <Link to={register ? '/sesion' : '/registro'} state={{ from: destination }}>
                {register ? 'Iniciar sesión' : 'Crear cuenta'}
              </Link>
            </p>
            <Link className="explore-link" to="/">
              Continuar sin cuenta
            </Link>
          </form>
        </main>
      </div>
      {candidate && <p className="auth-signed-in">Ya iniciaste sesión como {candidate.email}. <Link to="/">Ir al inicio</Link></p>}
    </>
  )
}
