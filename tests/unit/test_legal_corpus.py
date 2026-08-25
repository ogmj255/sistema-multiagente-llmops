import json
from pathlib import Path

import httpx
import pytest
from app.schemas.legal_corpus import LegalSource
from app.services import legal_corpus


def create_source(
    document_id: str,
    url: str,
) -> LegalSource:
    """Crea una fuente jurídica para las pruebas."""

    return LegalSource(
        document_id=document_id,
        title="Norma jurídica de prueba",
        jurisdiction="ecuador",
        issuing_body="Institución oficial",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url=url,
        topics=["data_protection"],
    )


def test_build_corpus_continues_after_download_error(
    tmp_path: Path,
) -> None:
    """Conserva los documentos válidos aunque otro falle."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path.endswith("/failed"):
            return httpx.Response(
                status_code=503,
                request=request,
            )

        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html"},
            content=(
                b"<html><body><main>"
                b"<h1>Ley organica</h1>"
                b"<p>Articulo 1. Objeto de la ley.</p>"
                b"</main></body></html>"
            ),
            request=request,
        )

    sources = [
        create_source(
            "valid-law",
            "https://example.com/valid",
        ),
        create_source(
            "failed-law",
            "https://example.com/failed",
        ),
    ]

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = legal_corpus.build_legal_corpus(
            sources=sources,
            raw_directory=tmp_path / "raw",
            processed_directory=tmp_path / "processed",
            client=client,
        )

    assert result.requested == 2
    assert result.completed == 1
    assert result.failed == 1
    assert result.documents[0].source.document_id == "valid-law"
    assert "Articulo 1" in result.documents[0].content
    assert result.errors[0].document_id == "failed-law"
    assert (
        tmp_path / "raw" / "valid-law.html"
    ).exists()
    assert (
        tmp_path / "processed" / "valid-law.json"
    ).exists()


def test_detect_pdf_document(
    monkeypatch,
) -> None:
    """Utiliza el extractor PDF cuando corresponde."""

    def fake_pdf_extractor(
        _content: bytes,
    ) -> str:
        return "Contenido juridico del PDF."

    monkeypatch.setattr(
        legal_corpus,
        "extract_pdf_text",
        fake_pdf_extractor,
    )

    text, content_type = (
        legal_corpus.extract_document_text(
            content=b"%PDF-document",
            content_type="application/pdf",
            source_url="https://example.com/law.pdf",
        )
    )

    assert text == "Contenido juridico del PDF."
    assert content_type == "application/pdf"


def test_reject_manifest_below_required_minimum(
    tmp_path: Path,
) -> None:
    """Rechaza un manifiesto con menos de 50 fuentes."""

    source = create_source(
        "single-law",
        "https://example.com/law",
    )
    manifest_path = tmp_path / "sources.json"
    manifest_path.write_text(
        json.dumps(
            [source.model_dump(mode="json")]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="mínimo de 50 documentos",
    ):
        legal_corpus.load_legal_sources(
            manifest_path
        )