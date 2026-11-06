"""Auditoría de aplicabilidad y RAG: pruebas sin OpenRouter."""

import hashlib
from types import SimpleNamespace

import pytest

from app.evaluation.pilot import canonical_sha256
from scripts import audit_v21_holdout_readonly as audit


def test_query_sha_maps_to_technical_clause_without_revealing_text():
    unit = SimpleNamespace(
        technical_id="ToS02-U001", original_text="Texto contractual fijo"
    )
    key = hashlib.sha256(
        "Cláusula: Texto contractual fijo".encode("utf-8")
    ).hexdigest()
    assert audit._id_mapping([unit]) == {key: "ToS02-U001"}


def test_identical_rag_content_excludes_distance():
    source = {
        "matches": [
            {
                "chunk_id": "sample_chunk_0001",
                "document_id": "sample",
                "content": "Derecho recuperado",
                "checksum": "c" * 64,
                "distance": 0.123456,
            }
        ]
    }
    a = {"response": source}
    b = {"response": {
        "matches": [{**source["matches"][0], "distance": 0.123457}]
    }}
    assert audit._match_signature(a) == audit._match_signature(b)


def test_corrupt_snapshot_rejected(monkeypatch, tmp_path):
    path = tmp_path / "rag.jsonl"
    row = {
        "configuration": {"query_sha256": "abcdef"},
        "response": {"status": "success", "matches": []},
    }
    row["response_sha256"] = canonical_sha256(row["response"])
    monkeypatch.setattr(audit, "read_jsonl", lambda _p: [row])
    assert len(audit._read_cache(path)) == 1
    row["response_sha256"] = "broken"
    with pytest.raises(ValueError, match="alterado"):
        audit._read_cache(path)


def test_duplicate_query_refused(monkeypatch, tmp_path):
    row = {
        "configuration": {"query_sha256": "abcdef"},
        "response": {"status": "success", "matches": []},
    }
    row["response_sha256"] = canonical_sha256(row["response"])
    monkeypatch.setattr(audit, "read_jsonl", lambda _p: [row, row])
    with pytest.raises(ValueError, match="repetida"):
        audit._read_cache(tmp_path / "rag.jsonl")
