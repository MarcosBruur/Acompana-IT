import asyncio

import pytest
from httpx import Request, Response
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import BadRequestError

from app.core.config import Settings, settings
from app.core.llm import chat_options, invalid_request_detail
from app.modules.interviews import router as interview_router
from app.modules.interviews import simulation
from app.modules.vacancies import analysis


def test_specific_models_override_shared_model_and_fall_back(monkeypatch):
    monkeypatch.delenv("OPENAI_VACANCY_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_INTERVIEW_MODEL", raising=False)
    shared = Settings(_env_file=None, openai_model="shared-model")
    assert shared.vacancy_model == "shared-model"
    assert shared.interview_model == "shared-model"

    monkeypatch.setenv("OPENAI_VACANCY_MODEL", "offer-model")
    monkeypatch.setenv("OPENAI_INTERVIEW_MODEL", "interview-model")
    separate = Settings(_env_file=None, openai_model="shared-model")
    assert separate.vacancy_model == "offer-model"
    assert separate.interview_model == "interview-model"

    monkeypatch.setenv("OPENAI_INTERVIEW_MODEL", "")
    assert Settings(_env_file=None, openai_model="shared-model").interview_model == "shared-model"


def test_each_workflow_uses_its_configured_model(monkeypatch):
    class Captured(Exception):
        pass

    seen = []

    class RecordingModel:
        def __init__(self, **kwargs):
            seen.append(kwargs["model"])

        def with_structured_output(self, _schema, *, method, strict):
            assert method == "json_schema" and strict is True
            raise Captured

    monkeypatch.setattr(settings, "openai_model", "shared-model")
    monkeypatch.setattr(settings, "openai_vacancy_model", "offer-model")
    monkeypatch.setattr(settings, "openai_interview_model", "interview-model")
    monkeypatch.setattr(analysis, "ChatOpenAI", RecordingModel)
    monkeypatch.setattr(simulation, "ChatOpenAI", RecordingModel)

    with pytest.raises(Captured):
        asyncio.run(analysis.analyze_offer("Puesto", None, "Descripción"))
    with pytest.raises(Captured):
        asyncio.run(simulation.generate_questions("Puesto", "Descripción", "", "conversation"))
    with pytest.raises(Captured):
        asyncio.run(simulation.evaluate_answer(
            "¿Pregunta?", "Referencia", "Respuesta", vacancy_title="Puesto",
            vacancy_description="Descripción", topic="Python", previous="",
        ))
    assert seen == ["offer-model", "interview-model", "interview-model"]


@pytest.mark.parametrize(("name", "uses_temperature"), [
    ("gpt-4.1-mini", True),
    ("gpt-6-luna", False),
    ("gpt-6.1-terra", False),
    ("gpt-5.4-mini", False),
    ("o3-mini", False),
])
def test_request_parameters_match_model_family(name, uses_temperature):
    options = chat_options(name, max_tokens=800, timeout=30)
    # Inspeccionar el payload construido por la versión instalada de LangChain, sin usar la red.
    model = ChatOpenAI(**{**options, "api_key": "dummy"})
    payload = model._get_request_payload([HumanMessage(content="Prueba")])
    assert ("temperature" in payload) is uses_temperature
    assert payload["max_completion_tokens"] == 800
    assert payload["model"] == name


def test_bad_request_is_actionable_without_echoing_provider_data():
    response = Response(400, request=Request("POST", "https://api.openai.com/v1/chat/completions"))
    error = BadRequestError("secret-provider-response", response=response,
                            body={"param": "temperature", "code": "unsupported_value"})
    detail = invalid_request_detail(error, "vacantes")
    assert "parámetros" in detail
    interview_error = interview_router.provider_error(error)
    assert interview_error.status_code == 503
    assert "secret-provider-response" not in interview_error.detail
    unknown = BadRequestError("secret-provider-response", response=response,
                              body={"param": "some-private-value"})
    assert "some-private-value" not in invalid_request_detail(unknown, "entrevistas")
