"""Validación y extracción en un proceso terminable, separado del worker HTTP."""

import io
from multiprocessing import get_context
from multiprocessing.connection import Connection
from time import monotonic

import psutil
from pypdf import PdfReader

from app.core.config import settings


class InvalidPdf(Exception):
    pass


def _parse(content: bytes, extract: bool, connection: Connection) -> None:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise InvalidPdf
        if extract:
            text = " ".join((page.extract_text() or "") for page in reader.pages[:12])
            connection.send((True, " ".join(text.split())[:5000]))
        else:
            connection.send((True, ""))
    except Exception:  # noqa: BLE001 — nunca enviar detalles del documento al proceso web.
        connection.send((False, ""))
    finally:
        connection.close()


def process_pdf(content: bytes, *, extract: bool = False) -> str:
    if len(content) > 5 * 1024 * 1024 or not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise InvalidPdf
    context = get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_parse, args=(content, extract, child), daemon=True)
    process.start()
    child.close()
    deadline = monotonic() + settings.pdf_timeout_seconds
    try:
        while process.is_alive():
            if monotonic() >= deadline:
                raise InvalidPdf
            try:
                if psutil.Process(process.pid).memory_info().rss > settings.pdf_memory_mb * 1024 * 1024:
                    raise InvalidPdf
            except psutil.NoSuchProcess:
                break
            process.join(timeout=0.05)
        if process.exitcode != 0 or not parent.poll(0.1):
            raise InvalidPdf
        valid, text = parent.recv()
        if not valid:
            raise InvalidPdf
        return text
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        parent.close()
