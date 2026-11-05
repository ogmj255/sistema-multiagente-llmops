"""Plan reproducible de la sección 3.7 del Capítulo III de la tesis."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from app.evaluation.groundtruth import GroundTruth

MODELS: Final[tuple[tuple[str, str], ...]] = (
    ("T1", "deepseek/deepseek-v4-flash-0731"),
    ("T2", "mistralai/mistral-large-2512"),
    ("T3", "moonshotai/kimi-k2.6"),
)

# Tabla 8 (corpus) y Tablas 21-22 (diseño), TesisCap3, 2026.
DOCUMENTS: Final[tuple[tuple[str, str, int], ...]] = (
    ("ToS01", "Holded", 21),
    ("ToS02", "OpenAI", 40),
    ("ToS03", "Canva", 73),
    ("ToS04", "Dropbox", 45),
    ("ToS05", "Elsevier ScienceDirect AI", 25),
    ("ToS06", "Shopify", 91),
    ("ToS07", "GitHub", 68),
    ("ToS08", "Figma", 61),
    ("ToS09", "Todoist", 75),
    ("ToS10", "Jotform", 48),
)
REPETITIONS: Final[int] = 3
EXPECTED_UNITS: Final[int] = sum(n for _, _, n in DOCUMENTS)


class ExperimentalDesignError(ValueError):
    """El corpus no corresponde al diseño experimental documentado."""


@dataclass(frozen=True, slots=True)
class ExperimentalTask:
    task_id: str
    combination_id: str
    document_id: str
    platform: str
    treatment: str
    model: str
    repetition: int
    unit_count: int


def make_experimental_plan(
    groundtruth: GroundTruth,
) -> dict[str, object]:
    """Crea las 90 ejecuciones previstas; NO realiza ninguna inferencia.

    ET01-ET30 identifica la combinación documento-modelo, tal como
    se definió en la Tabla 22. Cada combinación se repite tres veces.
    """
    counts = Counter(
        (unit.technical_id.split("-")[0], unit.platform)
        for unit in groundtruth.units
    )
    expected = {
        (document_id, platform): n
        for document_id, platform, n in DOCUMENTS
    }

    if len(groundtruth.units) != EXPECTED_UNITS or counts != expected:
        raise ExperimentalDesignError(
            "El CSV no coincide con los 10 documentos y las 547 "
            "unidades definidos en la Tabla 8 de la tesis."
        )

    tasks: list[ExperimentalTask] = []
    combination = 0
    for document_id, platform, unit_count in DOCUMENTS:
        for treatment, model in MODELS:
            combination += 1
            combination_id = f"ET{combination:02d}"
            for repetition in range(1, REPETITIONS + 1):
                tasks.append(
                    ExperimentalTask(
                        task_id=f"{combination_id}-R{repetition}",
                        combination_id=combination_id,
                        document_id=document_id,
                        platform=platform,
                        treatment=treatment,
                        model=model,
                        repetition=repetition,
                        unit_count=unit_count,
                    )
                )

    return {
        "dataset_fingerprint": groundtruth.fingerprint,
        "dataset_source_sha256": groundtruth.source_sha256,
        "repetitions": REPETITIONS,
        "documents": len(DOCUMENTS),
        "units": EXPECTED_UNITS,
        "treatments": [
            {"treatment": code, "model": model}
            for code, model in MODELS
        ],
        "combinations": combination,
        "executions": len(tasks),
        "expected_unit_predictions": sum(
            task.unit_count for task in tasks
        ),
        "status": "planned_not_executed",
        "tasks": [asdict(task) for task in tasks],
    }
