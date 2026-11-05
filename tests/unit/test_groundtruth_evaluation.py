"""Pruebas aisladas de integridad y métricas, sin depender de un LLM."""

import csv
import hashlib
from pathlib import Path

import pytest

from app.evaluation.groundtruth import (
    GroundTruthError,
    load_groundtruth_csv,
)
from app.evaluation.metrics import score_predictions


def write_dataset(path: Path, *, duplicate: bool = False) -> None:
    rows = [
        [
            "ToS01-U001", "Plataforma A", "Original íntegro <sin alterar>",
            "Evaluable", "potencialmente abusiva",
        ],
        [
            "ToS01-U002", "Plataforma A", "Título aislado",
            "No aplicable", "not_applicable",
        ],
        [
            "ToS01-U003", "Plataforma B", "Cláusula con ñ y €",
            "Evaluable", "no potencialmente abusiva",
        ],
    ]
    if duplicate:
        rows.append(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "ID técnico", "Plataforma", "Cláusula original completa",
            "Aplicabilidad", "Etiqueta final",
        ])
        writer.writerows(rows)


def test_import_preserves_text_and_hides_labels_from_model(tmp_path):
    path = tmp_path / "groundtruth.csv"
    write_dataset(path)

    gt = load_groundtruth_csv(path, expected_count=3)
    assert len(gt.units) == 3
    assert gt.units[0].original_text == "Original íntegro <sin alterar>"
    assert gt.units[0].text_sha256 == hashlib.sha256(
        b"Original \xc3\xadntegro <sin alterar>"
    ).hexdigest()
    assert gt.manifest()["platforms"] == {
        "Plataforma A": 2, "Plataforma B": 1,
    }
    assert set(gt.units[0].model_input()) == {"id", "platform", "text"}
    assert "potencialmente abusiva" not in gt.units[0].model_input().values()


def test_import_rejects_duplicates(tmp_path):
    path = tmp_path / "duplicate.csv"
    write_dataset(path, duplicate=True)
    with pytest.raises(GroundTruthError, match="duplicado"):
        load_groundtruth_csv(path, expected_count=None)


def test_import_rejects_unexpected_size(tmp_path):
    path = tmp_path / "small.csv"
    write_dataset(path)
    with pytest.raises(GroundTruthError, match="547"):
        load_groundtruth_csv(path)


def test_score_counts_missing_and_misclassified_predictions(tmp_path):
    path = tmp_path / "groundtruth.csv"
    write_dataset(path)
    gt = load_groundtruth_csv(path, expected_count=3)
    records = [
        {
            "id": "ToS01-U001", "model": "modelo-1",
            "dataset_fingerprint": gt.fingerprint,
            "status": "success",
            "prediction": "potencialmente abusiva",
        },
        {
            "id": "ToS01-U002", "model": "modelo-1",
            "dataset_fingerprint": gt.fingerprint,
            "status": "success",
            "prediction": "no potencialmente abusiva",
        },
    ]
    report = score_predictions(gt, records, model="modelo-1")
    assert report["all_units"]["total"] == 3
    assert report["all_units"]["correct"] == 1
    assert report["all_units"]["missing_or_invalid"] == 1
    assert report["all_units"]["accuracy"] == round(1 / 3, 6)
    assert report["all_units"]["confusion_matrix"][
        "no potencialmente abusiva"
    ]["__invalid__"] == 1
    assert report["evaluable_units"]["total"] == 2


def test_score_rejects_other_dataset_fingerprint(tmp_path):
    path = tmp_path / "groundtruth.csv"
    write_dataset(path)
    gt = load_groundtruth_csv(path, expected_count=3)
    with pytest.raises(ValueError, match="versión"):
        score_predictions(gt, [{
            "id": "ToS01-U001",
            "model": "modelo-1",
            "dataset_fingerprint": "incorrecta",
            "status": "success",
            "prediction": "potencialmente abusiva",
        }], model="modelo-1")
