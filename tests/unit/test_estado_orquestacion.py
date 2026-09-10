from uuid import UUID

from app.schemas.contract import ExtractionRequest
from app.schemas.orquestacion import create_initial_state


def make_request() -> ExtractionRequest:
    return ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )


def test_initial_state_preserves_request():
    request = make_request()

    state = create_initial_state(request)

    assert state["request"] == request
    assert state["jurisdiction"] == "ecuador"


def test_initial_state_starts_pending_extraction():
    state = create_initial_state(make_request())

    assert state["status"] == "pending"
    assert state["current_step"] == "extraction"
    assert state["current_clause_index"] == 0


def test_initial_state_has_no_previous_results():
    state = create_initial_state(make_request())

    assert state["extracted_contract"] is None
    assert state["preprocessed_contract"] is None
    assert state["clause_results"] == {}
    assert state["errors"] == []
    assert state["attempts"] == {}


def test_execution_identifiers_are_unique_uuids():
    first = create_initial_state(make_request())
    second = create_initial_state(make_request())

    assert UUID(first["execution_id"]).version == 4
    assert UUID(second["execution_id"]).version == 4
    assert first["execution_id"] != second["execution_id"]


def test_mutable_containers_are_not_shared():
    first = create_initial_state(make_request())
    second = create_initial_state(make_request())

    for field in ("clause_results", "errors", "attempts"):
        assert first[field] is not second[field]

    first["attempts"]["extraction"] = 1

    assert second["attempts"] == {}
