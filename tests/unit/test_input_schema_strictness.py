import pytest
from app.schemas.contract import ExtractionRequest
from app.schemas.knowledge import KnowledgeQuery
from pydantic import ValidationError


def test_extraction_request_rejects_unknown_fields() -> None:
    """Rechaza parámetros desconocidos en la entrada de extracción."""

    with pytest.raises(
        ValidationError,
    ) as exc_info:
        ExtractionRequest(
            url="https://example.com/terms",
            platfrom="Example",
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("platfrom",)


def test_knowledge_query_rejects_unknown_fields() -> None:
    """Rechaza parámetros desconocidos en consultas jurídicas."""

    with pytest.raises(
        ValidationError,
    ) as exc_info:
        KnowledgeQuery(
            query="protección de datos personales",
            topk=10,
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("topk",)


def test_knowledge_query_rejects_removed_filters() -> None:
    """Impide reintroducir filtros jurídicos en la consulta RAG."""

    removed_fields = (
        ("jurisdiction", "ecuador"),
        ("document_type", "law"),
    )

    for field, value in removed_fields:
        with pytest.raises(
            ValidationError,
        ) as exc_info:
            KnowledgeQuery(
                query="protección de datos personales",
                **{field: value},
            )

        errors = exc_info.value.errors()

        assert len(errors) == 1
        assert errors[0]["type"] == "extra_forbidden"
        assert errors[0]["loc"] == (field,)

