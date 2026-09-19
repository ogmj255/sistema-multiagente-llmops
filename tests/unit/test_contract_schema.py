from datetime import UTC, datetime

import pytest
from app.schemas.contract import ContractSection, ExtractedContract
from pydantic import ValidationError


def test_create_extracted_contract() -> None:
    raw_html = """
    <html lang="es">
        <body>
            <main>
                <h1>Términos de servicio</h1>
                <p>Contenido contractual de prueba.</p>
            </main>
        </body>
    </html>
    """

    contract = ExtractedContract(
        source_url="https://example.com/terms",
        platform="Plataforma de prueba",
        retrieved_at=datetime.now(UTC),
        extraction_method="httpx",
        raw_html=raw_html,
    )

    assert contract.platform == "Plataforma de prueba"
    assert contract.extraction_method == "httpx"
    assert "Contenido contractual de prueba." in contract.raw_html


def test_reject_section_with_invalid_order() -> None:
    with pytest.raises(ValidationError):
        ContractSection(
            order=0,
            heading="Sección incorrecta",
            content="Contenido de prueba.",
        )
