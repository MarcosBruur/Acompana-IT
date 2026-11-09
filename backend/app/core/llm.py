"""Parámetros compartidos y errores seguros para modelos de OpenAI."""

import re

from app.core.config import settings


def chat_options(model_name: str, *, max_tokens: int, timeout: int) -> dict:
    # Los modelos de razonamiento rechazan temperature cuando el esfuerzo no es 'none'.
    # No forzamos el esfuerzo: cada modelo conserva su valor predeterminado.
    reasoning = bool(re.match(r"^(?:gpt-(?:[5-9]|[1-9]\d+)(?:[.-]|$)|o\d+(?:-|$))",
                              model_name.casefold()))
    options = {
        "model": model_name,
        "api_key": settings.openai_api_key,
        "max_completion_tokens": max_tokens,
        "timeout": timeout,
        "max_retries": 0,
    }
    if not reasoning:
        options["temperature"] = 0
    return options


def invalid_request_detail(exc: Exception, task: str) -> str | None:
    """No incluir mensaje ni cuerpo de OpenAI: podrían contener datos del candidato."""
    status = getattr(exc, "status_code", None)
    if status in {403, 404}:
        return (f"El modelo de {task} configurado no está disponible para esta clave de OpenAI. "
                "Revisá el nombre y el acceso al modelo en backend/.env.")
    if status != 400:
        return None
    param = getattr(exc, "param", None)
    if param == "model":
        return (f"El modelo de {task} configurado fue rechazado por OpenAI. "
                "Revisá el nombre y el acceso al modelo en backend/.env.")
    if param in {"temperature", "max_tokens", "max_completion_tokens", "reasoning_effort"}:
        return (f"El modelo de {task} configurado no admite uno de los parámetros enviados. "
                "Elegí un modelo compatible o revisá su configuración en backend/.env.")
    return (f"El modelo de {task} configurado rechazó la solicitud. "
            "Verificá que admita salida estructurada JSON Schema estricta y que tu clave tenga acceso.")
