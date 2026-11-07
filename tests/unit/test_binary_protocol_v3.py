"""V3: referencia humana cerrada, sin LLM ni servicios externos.

Genera un corpus sintético de 547 filas para ejercitar hashes,
versionado, conteos y preservación del protocolo V2.
"""

from __future__ import annotations

import csv
import hashlib
import json

import pytest

from app.evaluation import binary_groundtruth as bg
from app.evaluation import readiness
from app.evaluation.groundtruth import load_groundtruth_csv


def _canonical_sha(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _fixture(tmp_path, monkeypatch):
    source = tmp_path / "ground_truth_547_v3.csv"
    labels = (
        ["no potencialmente abusiva"] * 318
        + ["potencialmente abusiva"] * 156
        + ["not_applicable"] * 73
    )
    rows = []
    for index, label in enumerate(labels, start=1):
        rows.append({
            "ID técnico": f"ToS01-U{index:03d}",
            "Plataforma": "Plataforma de prueba",
            "Cláusula original completa": f"Texto fijo {index}: ñ €",
            "Aplicabilidad": (
                "No aplicable" if label == "not_applicable" else "Evaluable"
            ),
            "Etiqueta final": label,
        })
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    base = load_groundtruth_csv(source)
    text_seq = [
        {"id": u.technical_id, "platform": u.platform, "text": u.original_text}
        for u in base.units
    ]
    canonical = [
        {
            "id": u.technical_id,
            "platform": u.platform,
            "text": u.original_text,
            "applicability": u.applicability,
            "label": u.label,
        }
        for u in base.units
    ]
    monkeypatch.setattr(bg, "V3_SOURCE_FINGERPRINT", base.fingerprint)
    monkeypatch.setattr(bg, "V3_SOURCE_SHA256", base.source_sha256)
    monkeypatch.setattr(
        bg, "V3_BINARY_FINGERPRINT",
        _canonical_sha({
            "protocol": bg.V3_PROTOCOL,
            "base_fingerprint": base.fingerprint,
            "rows": canonical,
        })
    )
    monkeypatch.setattr(
        bg, "V3_TEXT_SEQUENCE_FINGERPRINT", _canonical_sha(text_seq)
    )
    return source


def test_v3_validates_binary_counts_and_preserves_original(tmp_path, monkeypatch):
    source = _fixture(tmp_path, monkeypatch)
    dataset = bg.load_binary_groundtruth_v3(source)
    report = bg.binary_manifest_v3(dataset)
    assert report["protocol"] == "NPA-PA-v3.0"
    assert report["classification_labels"] == {"NPA": 318, "PA": 156}
    assert report["applicability"]["not_applicable"] == 73
    assert set(u.label for u in dataset.units) == set(bg.BINARY_LABELS)
    assert dataset.units[0].original_text == "Texto fijo 1: ñ €"


def test_v3_rejects_label_changes_even_when_text_is_identical(tmp_path, monkeypatch):
    source = _fixture(tmp_path, monkeypatch)
    original = source.read_text(encoding="utf-8")
    modified = original.replace(
        ",Evaluable,no potencialmente abusiva\n",
        ",Evaluable,potencialmente abusiva\n", 1,
    )
    assert modified != original
    source.write_text(modified, encoding="utf-8")
    with pytest.raises(ValueError, match="etiquetas aprobadas"):
        bg.load_binary_groundtruth_v3(source)


def test_v3_rejects_byte_reencoding_despite_equal_semantic_fingerprint(tmp_path, monkeypatch):
    source = _fixture(tmp_path, monkeypatch)
    content = source.read_bytes()
    source.write_bytes(b"\xef\xbb\xbf" + content)
    with pytest.raises(ValueError, match="byte a byte"):
        bg.load_binary_groundtruth_v3(source)


def test_v3_does_not_reuse_v2_manifest_and_paths():
    assert bg.V3_PROTOCOL != bg.BINARY_PROTOCOL
    assert bg.V3_BINARY_FINGERPRINT != bg.V1_DATASET_FINGERPRINT
    assert readiness._version_config("v2") == (
        "NPA-PA-v2.0", "v2_binary_preflight_manifest.json",
        "ground_truth_547.csv",
    )
    assert readiness._version_config("v3") == (
        "NPA-PA-v3.0", "v3_binary_preflight_manifest.json",
        "ground_truth_547_v3.csv",
    )
    with pytest.raises(readiness.PreflightError, match="no admitida"):
        readiness._version_config("v4")


def test_v3_is_opt_in_and_v2_remains_default():
    assert bg.load_versioned_binary_groundtruth.__kwdefaults__ == {
        "version": "v2"
    }
    with pytest.raises(ValueError, match="no permitida"):
        bg.load_versioned_binary_groundtruth("does-not-matter.csv", version="v4")
