export function required(value: string): string | undefined {
  if (!value.trim()) return 'Este campo es obligatorio.'
}

export function validateEmail(value: string): string | undefined {
  const empty = required(value)
  if (empty) return empty
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) || value.length > 320) {
    return 'Ingresá un correo electrónico válido.'
  }
}

export function validatePassword(value: string): string | undefined {
  const empty = required(value)
  if (empty) return empty
  if (value.length < 8 || value.length > 1024 || !/[A-Z]/.test(value) || !/[0-9]/.test(value) || !/[^A-Za-z0-9]/.test(value)) {
    return 'Usá al menos 8 caracteres, una mayúscula, un número y un carácter especial.'
  }
}

export function validateConfirmation(value: string, password: string): string | undefined {
  const empty = required(value)
  if (empty) return empty
  if (value !== password) return 'Las contraseñas deben coincidir.'
}
