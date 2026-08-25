
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.schemas.legal_corpus import (
    CorpusBuildError,
    CorpusBuildResult,
    LegalDocument,
    LegalSource,
)

USER_AGENT = (
    "sistema-multiagente-llmops/1.0 "
    "(academic legal corpus)"
)


def normalize_document_text(value: str) -> str:
    """Normaliza el texto extraído de un documento jurídico."""

    lines = [
        line.strip()
        for line in value.splitlines()
        if line.strip()
    ]
    return "\n".join(lines)


def extract_html_text(content: bytes) -> str:
    """Extrae el contenido principal de un documento HTML."""

    soup = BeautifulSoup(content, "html.parser")

    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
        ]
    ):
        element.decompose()

    container = (
        soup.find("main")
        or soup.find("article")
        or soup.body
        or soup
    )

    return normalize_document_text(
        container.get_text("\n", strip=True)
    )


def extract_pdf_text(content: bytes) -> str:
    """Extrae texto de un PDF con contenido seleccionable."""

    reader = PdfReader(BytesIO(content))
    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )
    return normalize_document_text(text)


def load_legal_sources(
    manifest_path: Path,
    minimum_documents: int = 50,
) -> list[LegalSource]:
    """Carga y valida las fuentes definidas en el manifiesto."""

    if minimum_documents < 1:
        raise ValueError(
            "El mínimo de documentos debe ser positivo."
        )

    data = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if not isinstance(data, list):
        raise TypeError(
            "El manifiesto debe contener una lista."
        )

    sources = [
        LegalSource.model_validate(item)
        for item in data
    ]

    if len(sources) < minimum_documents:
        raise ValueError(
            "El manifiesto no contiene el mínimo "
            f"de {minimum_documents} documentos."
        )

    identifiers = [
        source.document_id
        for source in sources
    ]

    if len(identifiers) != len(set(identifiers)):
        raise ValueError(
            "El manifiesto contiene identificadores duplicados."
        )

    return sources


def extract_document_text(
    content: bytes,
    content_type: str,
    source_url: str,
) -> tuple[str, str]:
    """Selecciona el extractor según el contenido recibido."""

    is_pdf = (
        content.startswith(b"%PDF")
        or "application/pdf" in content_type
        or source_url.lower().endswith(".pdf")
    )

    if is_pdf:
        text = extract_pdf_text(content)
        normalized_type = "application/pdf"
    else:
        text = extract_html_text(content)
        normalized_type = "text/html"

    if not text:
        raise ValueError(
            "El documento no contiene texto utilizable."
        )

    return text, normalized_type


def process_legal_source(
    source: LegalSource,
    client: httpx.Client,
    raw_directory: Path,
    processed_directory: Path,
) -> LegalDocument:
    """Descarga, extrae y conserva un documento jurídico."""

    response = client.get(
    str(source.source_url),
    headers={
        "Accept": (
            "application/xhtml+xml, "
            "text/html;q=0.9, "
            "application/pdf;q=0.8, "
            "*/*;q=0.1"
        ),
        "Accept-Language": source.language,
    },
    )
    response.raise_for_status()

    text, content_type = extract_document_text(
        response.content,
        response.headers.get("content-type", ""),
        str(source.source_url),
    )

    checksum = hashlib.sha256(
        response.content
    ).hexdigest()

    extension = (
        ".pdf"
        if content_type == "application/pdf"
        else ".html"
    )

    raw_path = (
        raw_directory
        / f"{source.document_id}{extension}"
    )
    processed_path = (
        processed_directory
        / f"{source.document_id}.json"
    )

    raw_path.write_bytes(response.content)

    document = LegalDocument(
        source=source,
        retrieved_at=datetime.now(UTC),
        content_type=content_type,
        checksum=checksum,
        content=text,
        raw_path=str(raw_path),
        processed_path=str(processed_path),
    )

    processed_path.write_text(
        json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return document


def build_legal_corpus(
    sources: list[LegalSource],
    raw_directory: Path,
    processed_directory: Path,
    client: httpx.Client | None = None,
) -> CorpusBuildResult:
    """Construye el corpus sin detenerse por errores individuales."""

    raw_directory.mkdir(parents=True, exist_ok=True)
    processed_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    managed_client = client is None
    active_client = client or httpx.Client(
        follow_redirects=True,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )

    documents: list[LegalDocument] = []
    errors: list[CorpusBuildError] = []

    try:
        for source in sources:
            try:
                document = process_legal_source(
                    source,
                    active_client,
                    raw_directory,
                    processed_directory,
                )
                documents.append(document)
            except (
                httpx.HTTPError,
                OSError,
                PdfReadError,
                ValueError,
            ) as error:
                errors.append(
                    CorpusBuildError(
                        document_id=source.document_id,
                        source_url=source.source_url,
                        error=str(error),
                    )
                )
    finally:
        if managed_client:
            active_client.close()

    return CorpusBuildResult(
        requested=len(sources),
        completed=len(documents),
        failed=len(errors),
        documents=documents,
        errors=errors,
    )
