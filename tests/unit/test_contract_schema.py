from datetime import UTC, datetime

import pytest
from app.schemas.contract import ContractSection, ExtractedContract
from pydantic import ValidationError


def test_create_extracted_contract() -> None:
    section = ContractSection(
        order=1,
        heading="Condiciones de uso",
        content="El usuario deberá cumplir las condiciones establecidas.",
    )

    contract = ExtractedContract(
        source_url="https://example.com/terms",
        platform="Plataforma de prueba",
        title="Términos de servicio",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="es",
        sections=[section],
        full_text=section.content,
    )

    assert contract.platform == "Plataforma de prueba"
    assert len(contract.sections) == 1
    assert contract.sections[0].order == 1


def test_reject_section_with_invalid_order() -> None:
    with pytest.raises(ValidationError):
        ContractSection(
            order=0,
            heading="Sección incorrecta",
            content="Contenido de prueba.",
        )
