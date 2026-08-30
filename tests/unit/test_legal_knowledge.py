import json
from datetime import UTC, datetime
from itertools import pairwise

from app.schemas.legal_corpus import (
    LegalDocument,
    LegalSource,
)
from app.services.legal_knowledge import (
    prepare_legal_chunks,
    prepare_legal_document,
    split_legal_text,
)


def create_legal_document() -> LegalDocument:
    """Crea un documento jurídico válido para pruebas."""

    source = LegalSource(
        document_id="ec_test_law",
        title="Ley de prueba",
        jurisdiction="ecuador",
        issuing_body="Asamblea Nacional",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url="https://example.com/law",
        topics=["protección de datos"],
    )

    return LegalDocument(
        source=source,
        retrieved_at=datetime.now(UTC),
        content_type="text/html",
        checksum="a" * 64,
        content=("Artículo 1. Protección de datos personales. " * 100),
        raw_path="data/raw/legal/ec_test_law.html",
        processed_path=("data/processed/legal/ec_test_law.json"),
    )


def test_split_legal_text_respects_limits() -> None:
    """Conserva orden, límites y solapamiento."""

    text = " ".join(f"palabra{index}" for index in range(100))

    chunks = split_legal_text(
        text,
        max_length=100,
        overlap=20,
    )

    assert len(chunks) > 1
    assert all(1 <= len(chunk) <= 100 for chunk in chunks)
    assert chunks == split_legal_text(
        text,
        max_length=100,
        overlap=20,
    )

    for previous, current in pairwise(chunks):
        assert set(previous.split()) & set(current.split())


def test_split_preserves_legal_boundaries() -> None:
    """Evita cortes internos en unidades jurídicas."""

    text = (
        "Art. 43.- Cláusulas Prohibidas.- "
        "Son nulas de pleno derecho las cláusulas "
        "contractuales siguientes:\n"
        "1. Eximan o limiten la responsabilidad "
        "del proveedor por los servicios prestados;\n"
        "2. Impliquen renuncia a los derechos "
        "reconocidos a los consumidores;\n"
        "3. Inviertan la carga de la prueba en "
        "perjuicio del consumidor.\n"
        "Art. 44.- El consumidor podrá terminar "
        "anticipadamente el contrato."
    )

    chunks = split_legal_text(
        text,
        max_length=220,
        overlap=50,
    )

    valid_starts = (
        "Art. 43",
        "1.",
        "2.",
        "3.",
        "Art. 44",
    )
    valid_ends = (".", ";", ":")

    assert len(chunks) > 1
    assert all(len(chunk) <= 220 for chunk in chunks)
    assert all(chunk.startswith(valid_starts) for chunk in chunks)
    assert all(chunk.endswith(valid_ends) for chunk in chunks)


def test_prepare_legal_document() -> None:
    """Genera identificadores y conserva metadatos."""

    chunks = prepare_legal_document(create_legal_document())

    assert len(chunks) > 1
    assert chunks[0].chunk_id == ("ec_test_law_chunk_0000")
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.document_id == "ec_test_law" for chunk in chunks)
    assert all(chunk.jurisdiction == "ecuador" for chunk in chunks)
    assert all(chunk.topics == "protección de datos" for chunk in chunks)


def test_prepare_chunks_continues_after_error(
    tmp_path,
) -> None:
    """Registra documentos inválidos sin detener el corpus."""

    processed_directory = tmp_path / "legal"
    processed_directory.mkdir()

    valid_path = processed_directory / "valid.json"
    valid_path.write_text(
        create_legal_document().model_dump_json(),
        encoding="utf-8",
    )

    invalid_path = processed_directory / "invalid.json"
    invalid_path.write_text(
        "{invalid",
        encoding="utf-8",
    )

    output_path = tmp_path / "legal_chunks.jsonl"

    chunks, errors = prepare_legal_chunks(
        processed_directory,
        output_path,
        minimum_documents=2,
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert chunks
    assert len(errors) == 1
    assert errors[0].startswith("invalid.json:")
    assert len(lines) == len(chunks)
    assert json.loads(lines[0])["document_id"] == ("ec_test_law")
