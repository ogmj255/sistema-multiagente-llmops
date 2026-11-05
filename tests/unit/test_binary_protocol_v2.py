"""V2: ground truth congelado, salida binaria y aplicabilidad separada."""

import pytest
from pydantic import ValidationError

from app.evaluation.binary_groundtruth import (
    BINARY_LABELS, BINARY_MAPPING, BINARY_PROTOCOL,
    V1_DATASET_FINGERPRINT, project_binary_groundtruth,
)
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit
from app.schemas.legal_analysis import ClauseAnalysisDecision


def fixture_source():
    labels = [
        "not_applicable",
        "no potencialmente abusiva",
        "potencialmente abusiva",
        "indicios fuertes de abusividad",
    ]
    rows = tuple(
        GroundTruthUnit(
            technical_id=f"ToS01-U{i:03d}",
            platform="Holded",
            original_text=f"Texto original {i}",
            applicability="No aplicable" if i == 1 else "Evaluable",
            label=label,
            text_sha256=str(i) * 64,
        )
        for i, label in enumerate(labels, 1)
    )
    return GroundTruth(
        units=rows,
        fingerprint=V1_DATASET_FINGERPRINT,
        source_sha256="0" * 64,
    )


def test_binary_projection_preserves_all_text_and_v1_reference():
    original = fixture_source()
    projected = project_binary_groundtruth(original)
    assert projected.fingerprint != original.fingerprint
    assert projected.source_sha256 == original.source_sha256
    assert [u.original_text for u in projected.units] == [
        u.original_text for u in original.units
    ]
    assert [u.label for u in projected.units] == [
        "not_applicable",
        "no potencialmente abusiva",
        "potencialmente abusiva",
        "potencialmente abusiva",
    ]
    assert original.units[-1].label == "indicios fuertes de abusividad"
    assert set(u.label for u in projected.units).issubset(BINARY_LABELS)
    assert len(BINARY_MAPPING) == 4
    assert BINARY_PROTOCOL == "NPA-PA-v2.0"


def test_binary_projection_rejects_unapproved_source():
    raw = fixture_source()
    with pytest.raises(ValueError, match="huella"):
        project_binary_groundtruth(GroundTruth(
            units=raw.units,
            fingerprint="wrong",
            source_sha256=raw.source_sha256,
        ))


def valid_decision(**overrides):
    values = {
        "category": "Responsabilidad",
        "clause_type": "Limitación",
        "target": "usuario",
        "classification": "potentially_abusive",
        "analysis_status": "classified",
        "justification": "Puede existir un desequilibrio.",
        "evidence_sufficiency": "insufficient",
        "legal_basis_indices": [],
    }
    return ClauseAnalysisDecision(**{**values, **overrides})


def test_legal_decision_allows_only_npa_pa():
    assert valid_decision().classification == "potentially_abusive"
    assert valid_decision(
        classification="not_potentially_abusive"
    ).classification == "not_potentially_abusive"
    with pytest.raises(ValidationError):
        valid_decision(classification="strong_indications_of_abusiveness")


def test_not_applicable_is_not_third_legal_class():
    assert valid_decision(
        classification=None, analysis_status="not_applicable"
    ).classification is None
    with pytest.raises(ValidationError):
        valid_decision(
            classification="potentially_abusive",
            analysis_status="not_applicable",
        )
