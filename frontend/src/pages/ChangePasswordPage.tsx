import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { FieldError } from '../components/FieldError'
import { useAuth } from '../features/auth-context'
import { required, validateConfirmation, validatePassword } from '../features/auth-validation'
import { AuthRequestError, authRequest, type Candidate } from '../services/auth'

type RenewalField = 'current_password' | 'new_password' | 'confirm_password'
type Values = Record<RenewalField, string>
type Errors = Partial<Record<RenewalField, string>>
const initialValues: Values = { current_password: '', new_password: '', confirm_password: '' }

function validateField(name: RenewalField, values: Values): string | undefined {
  if (name === 'current_password') return required(values[name])
  if (name === 'new_password') return validatePassword(values[name])
  return validateConfirmation(values.confirm_password, values.new_password)
}

export function ChangePasswordPage() {
  const [values, setValues] = useState<Values>(initialValues)
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const { candidate, setCandidate } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const destination = (location.state as { from?: string } | null)?.from ?? '/'

  function updateField(name: RenewalField, value: string) {
    const next = { ...values, [name]: value }
    setValues(next)
    setFormError('')
    setErrors((current) => ({
      ...current,
      [name]: current[name] ? validateField(name, next) : undefined,
      ...(name === 'new_password' && (next.confirm_password || current.confirm_password)
        ? { confirm_password: validateField('confirm_password', next) }
        : {}),
    }))
  }

  function field(name: RenewalField, label: string, autoComplete: string) {
    const id = `renewal-${name}`
    return (
      <div className="field">
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          name={name}
          type="password"
          autoComplete={autoComplete}
          required
          value={values[name]}
          onChange={(event) => updateField(name, event.target.value)}
          onBlur={() => setErrors((current) => ({ ...current, [name]: validateField(name, values) }))}
          aria-invalid={Boolean(errors[name])}
          aria-describedby={errors[name] ? `${id}-error` : undefined}
        />
        <FieldError id={`${id}-error`} message={errors[name]} />
      </div>
    )
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors: Errors = {}
    for (const name of ['current_password', 'new_password', 'confirm_password'] as const) {
      nextErrors[name] = validateField(name, values)
    }
    setErrors(nextErrors)
    if (Object.values(nextErrors).some(Boolean)) return
    setBusy(true)
    setFormError('')
    try {
      const result = await authRequest<Candidate>('/change-password', {
        method: 'POST',
        body: JSON.stringify(values),
      })
      setCandidate(result)
      navigate(destination, { replace: true })
    } catch (error) {
      if (error instanceof AuthRequestError) {
        const serverFields: Errors = {}
        for (const name of ['current_password', 'new_password', 'confirm_password'] as const) {
          if (error.fieldErrors[name]) serverFields[name] = error.fieldErrors[name]
        }
        if (error.status === 401) serverFields.current_password = error.message
        if (error.status === 422 && !Object.values(serverFields).some(Boolean)) {
          serverFields.new_password = error.message
        }
        setErrors(serverFields)
        if (!Object.values(serverFields).some(Boolean)) setFormError(error.message)
      } else {
        setFormError('No se pudo conectar. Intentá de nuevo.')
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="password-page">
      <form className="panel password-form" onSubmit={submit} noValidate>
        <h1>Cambiar contraseña</h1>
        <p>{candidate?.password_expired ? 'Tu contraseña cumplió 200 días. Cambiala para continuar.' : 'Actualizá tu contraseña.'}</p>
        {field('current_password', 'Contraseña actual', 'current-password')}
        {field('new_password', 'Nueva contraseña', 'new-password')}
        {field('confirm_password', 'Confirmar nueva contraseña', 'new-password')}
        <p>Mínimo 8 caracteres, mayúscula, número y carácter especial. Debe ser distinta de la anterior.</p>
        <FieldError id="renewal-form-error" message={formError} />
        <button className="primary" disabled={busy}>{busy ? 'Guardando…' : 'Cambiar contraseña'}</button>
      </form>
    </main>
  )
}
