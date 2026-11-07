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



def test_v3_preflight_requires_explicit_prompt_approval(tmp_path):
    with pytest.raises(readiness.PreflightError, match="Falta aprobar"):
        readiness._approved_v3_prompt(tmp_path)


def test_v3_preflight_rejects_mismatched_prompt_source(tmp_path):
    # Probar el rechazo por SHA, no por una versión ajena al prompt activo.
    prompt = (
        __import__("pathlib").Path(readiness.__file__).resolve().parents[1]
        / "prompts" / "legal_analysis.py"
    )
    selection = {
        "prompt_version": _actual_prompt_version(prompt),
        "prompt_source_sha256": "0" * 64,
        "approved_by": "Investigador",
        "approved_at": "2026-11-06",
        "selection_rationale": "Justificación de selección experimental.",
    }
    (tmp_path / "v3_final_prompt_selection.json").write_text(
        json.dumps(selection), encoding="utf-8"
    )
    with pytest.raises(readiness.PreflightError, match="no coincide"):
        readiness._approved_v3_prompt(tmp_path)


def _actual_prompt_version(prompt):
    # La identidad Git debe ser estable con checkouts Windows (CRLF).
    content = prompt.read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    ).hexdigest()
    versions = {
        "591b13b8a663c83891812ea6deebaf1ceb4685bd": "V2",
        "5be7988b570bef4f72365f6c9b2d1f2f8a0ce9fb": "V2.1",
    }
    return versions[blob]


def test_v3_approval_fingerprint_must_match_code(tmp_path):
    prompt = (
        __import__("pathlib").Path(readiness.__file__).resolve().parents[1]
        / "prompts" / "legal_analysis.py"
    )
    selection = {
        "prompt_version": _actual_prompt_version(prompt),
        "prompt_source_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
        "approved_by": "Investigador",
        "approved_at": "2026-11-06",
        "selection_rationale": "Selección explícita solo para prueba unitaria.",
    }
    (tmp_path / "v3_final_prompt_selection.json").write_text(
        json.dumps(selection), encoding="utf-8"
    )
    assert readiness._approved_v3_prompt(tmp_path) == selection



def test_v3_approval_accepts_equivalent_lf_crlf_checkout(tmp_path):
    # Una aprobación emitida en Windows debe validarse también en Linux,
    # sin aceptar alteraciones del contenido ni de la identidad Git.
    prompt = (
        __import__("pathlib").Path(readiness.__file__).resolve().parents[1]
        / "prompts" / "legal_analysis.py"
    )
    original = prompt.read_bytes()
    canonical_lf = original.replace(b"\r\n", b"\n")
    alternate = (
        canonical_lf if original != canonical_lf
        else canonical_lf.replace(b"\n", b"\r\n")
    )
    assert alternate != original
    selection = {
        "prompt_version": _actual_prompt_version(prompt),
        "prompt_source_sha256": hashlib.sha256(alternate).hexdigest(),
        "approved_by": "Investigador",
        "approved_at": "2026-11-06",
        "selection_rationale": "Prueba de equivalencia de checkout LF/CRLF.",
    }
    (tmp_path / "v3_final_prompt_selection.json").write_text(
        json.dumps(selection), encoding="utf-8"
    )
    assert readiness._approved_v3_prompt(tmp_path) == selection


def test_prompt_version_cannot_be_mislabelled(tmp_path):
    prompt = (
        __import__("pathlib").Path(readiness.__file__).resolve().parents[1]
        / "prompts" / "legal_analysis.py"
    )
    selection = {
        "prompt_version": (
            "V2.1" if _actual_prompt_version(prompt) == "V2" else "V2"
        ),
        "prompt_source_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
        "approved_by": "Investigador",
        "approved_at": "2026-11-06",
        "selection_rationale": "Test que detecta identidad incorrecta.",
    }
    (tmp_path / "v3_final_prompt_selection.json").write_text(
        json.dumps(selection), encoding="utf-8"
    )
    # Ninguna versión del prompt puede registrarse con la identidad opuesta.
    with pytest.raises(readiness.PreflightError, match="no corresponde"):
        readiness._approved_v3_prompt(tmp_path)
