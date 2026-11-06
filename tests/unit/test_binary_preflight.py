"""Preflight V2: invariantes reproducibles y ninguna llamada OpenRouter."""

import json
from types import SimpleNamespace

import pytest

from app.evaluation import readiness


def test_preflight_manifest_is_frozen_and_changes_blocked(tmp_path, monkeypatch):
    stable = {
        "protocol": readiness.PROTOCOL,
        "dataset_fingerprint": "a" * 64,
        "config_sha256": "b" * 64,
        "code_sha256": "c" * 64,
        "rag": {"collection": "legal_knowledge", "chunks": 25,
                "collection_sha256": "d" * 64},
    }
    monkeypatch.setattr(
        readiness,
        "create_readiness_manifest",
        lambda _path: dict(stable),
    )
    first = readiness.freeze_readiness(tmp_path)
    assert first["environment"] == stable
    assert len(first["fingerprint"]) == 64
    assert readiness.verify_readiness(tmp_path) == stable
    same = readiness.freeze_readiness(tmp_path)
    assert same == first

    stable["rag"] = {
        "collection": "legal_knowledge", "chunks": 25,
        "collection_sha256": "e" * 64,
    }
    with pytest.raises(readiness.PreflightError, match="cambió"):
        readiness.verify_readiness(tmp_path)
    with pytest.raises(readiness.PreflightError, match="cambió"):
        readiness.freeze_readiness(tmp_path)


def test_preflight_rejects_missing_or_corrupted_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        readiness,
        "create_readiness_manifest",
        lambda _folder: {"fingerprint": "a"},
    )
    with pytest.raises(readiness.PreflightError, match="Falta"):
        readiness.verify_readiness(tmp_path)
    path = tmp_path / readiness.MANIFEST_FILENAME
    path.write_text("{", encoding="utf-8")
    with pytest.raises(readiness.PreflightError, match="no es válido"):
        readiness.verify_readiness(tmp_path)


def test_chroma_inventory_is_read_only_and_has_consistent_digest(monkeypatch):
    seen = []

    class FakeCollection:
        metadata = {
            "embedding_model": "fake-embedding:1",
            "embedding_dimensions": 4,
        }
        def count(self):
            return 2
        def get(self, *, limit, offset, include):
            seen.append((limit, offset, include))
            rows = [
                ("id1", "Artículo uno", {"source": "A"}),
                ("id2", "Artículo dos", {"source": "B"}),
            ][offset:offset+limit]
            return {
                "ids": [row[0] for row in rows],
                "documents": [row[1] for row in rows],
                "metadatas": [row[2] for row in rows],
                "embeddings": [
                    [float(i+1), float(i+2), float(i+3), float(i+4)]
                    for i, row in enumerate(rows)
                ],
            }

    class FakeClient:
        def get_collection(self, *, name):
            assert name == "legal_knowledge"
            return FakeCollection()
        def get_or_create_collection(self, *args, **kwargs):
            raise AssertionError("El preflight no debe crear colecciones.")

    monkeypatch.setattr(
        readiness, "settings",
        SimpleNamespace(
            chroma_collection="legal_knowledge",
            ollama_embedding_model="fake-embedding:1",
            ollama_embedding_dimensions=4,
        ),
    )
    monkeypatch.setattr(
        readiness, "create_chroma_client",
        lambda: FakeClient(),
    )
    result = readiness._collection_inventory()
    assert result["chunks"] == 2
    assert len(result["collection_sha256"]) == 64
    assert seen == [(2, 0, ["documents", "metadatas", "embeddings"])]

    FakeCollection.metadata = {
        "embedding_model": "another-embedding",
        "embedding_dimensions": 4,
    }
    with pytest.raises(readiness.PreflightError, match="embeddings"):
        readiness._collection_inventory()
