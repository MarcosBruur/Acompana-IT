import io

import pytest
from pypdf import PdfWriter

from app.core.config import settings
from app.core.pdf_processing import InvalidPdf, process_pdf


def blank_pdf() -> bytes:
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def test_pdf_parser_runs_in_terminable_process(monkeypatch):
    content = blank_pdf()
    assert process_pdf(content) == ""
    monkeypatch.setattr(settings, "pdf_timeout_seconds", 0)
    with pytest.raises(InvalidPdf):
        process_pdf(content)


def test_pdf_parser_rejects_corrupt_data():
    with pytest.raises(InvalidPdf):
        process_pdf(b"%PDF-falso\n%%EOF")
