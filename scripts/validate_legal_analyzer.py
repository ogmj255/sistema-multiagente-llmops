import argparse
import json
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from app.agents.legal_analyzer_agent import (
    run_legal_analyzer_agent,
)
from app.core.config import settings
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause

DATASET_PATH = Path(
    "data/validation/legal_analysis_cases.json"
)
RESULTS_PATH = Path(
    "data/validation/legal_analysis_results.json"
)


def main() -> None:
    """Ejecuta la validación funcional del analizador."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
    )
    args = parser.parse_args()
    limit = args.limit
    case_ids = set(args.case_id)

    dataset = json.loads(
        DATASET_PATH.read_text(
            encoding="utf-8"
        )
    )
    cases = dataset["cases"]

    if case_ids:
        cases = [
            case
            for case in cases
            if case["case_id"] in case_ids
        ]

        found_ids = {
            case["case_id"]
            for case in cases
        }
        missing_ids = case_ids - found_ids

        if missing_ids:
            raise ValueError(
                "Casos no encontrados: "
                + ", ".join(sorted(missing_ids))
            )

    if limit is not None:
        if limit < 1:
            raise ValueError(
                "--limit debe ser mayor que cero."
            )
        cases = cases[:limit]

    results = []

    for position, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"[{position}/{len(cases)}] "
            f"{case['case_id']}",
            flush=True,
        )

        request = ClauseAnalysisRequest(
            source_url=(
                "https://validation.example/terms"
            ),
            platform="Validación TIT-48",
            language="es",
            clause=ProcessedClause(
                order=position,
                original_order=position,
                heading=case["heading"],
                heading_level=2,
                content=case["content"],
            ),
        )

        started = perf_counter()

        try:
            response = run_legal_analyzer_agent(
                request
            )

            elapsed = round(
                perf_counter() - started,
                3,
            )

            if (
                response.status != "success"
                or response.result is None
            ):
                raise RuntimeError(
                    response.error
                    or "Respuesta sin resultado."
                )

            assessment = response.result
            expected = case["expected"]

            actual_documents = {
                basis.document_id
                for basis in assessment.legal_basis
            }
            expected_documents = set(
                expected["document_ids"]
            )

            document_coverage = (
                expected_documents.issubset(
                    actual_documents
                )
                if expected_documents
                else None
            )

            semantic_structure = all(
                isinstance(value, str)
                and bool(value.strip())
                for value in (
                    assessment.category,
                    assessment.clause_type,
                    assessment.target,
                )
            )

            if (
                assessment.analysis_status
                == "not_applicable"
            ):
                basis_structure = (
                    assessment.classification is None
                    and not assessment.legal_basis
                )
            elif (
                assessment.evidence_sufficiency
                in {"sufficient", "partial"}
            ):
                basis_structure = bool(
                    assessment.legal_basis
                )
            else:
                basis_structure = (
                    not assessment.legal_basis
                )

            checks = {
                "classification": (
                    assessment.classification
                    == expected["classification"]
                ),
                "analysis_status": (
                    assessment.analysis_status
                    == expected["analysis_status"]
                ),
                "expected_document_coverage": (
                    document_coverage
                ),
                "semantic_structure": (
                    semantic_structure
                ),
                "basis_structure": (
                    basis_structure
                ),
            }

            core_checks = [
                checks["classification"],
                checks["analysis_status"],
                checks["semantic_structure"],
                checks["basis_structure"],
            ]

            result = {
                "case_id": case["case_id"],
                "duration_seconds": elapsed,
                "execution_success": True,
                "field_match": all(
                    core_checks
                ),
                "expected": expected,
                "actual": assessment.model_dump(
                    mode="json"
                ),
                "checks": checks,
                "manual_legal_review_required": True,
                "error": None,
            }

        except Exception as error:  # noqa: BLE001
            elapsed = round(
                perf_counter() - started,
                3,
            )

            result = {
                "case_id": case["case_id"],
                "duration_seconds": elapsed,
                "execution_success": False,
                "field_match": False,
                "manual_legal_review_required": True,
                "expected": case["expected"],
                "actual": None,
                "checks": {},
                "error": (
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
            }

        results.append(result)

        print(
            "  estado:",
            (
                "OK"
                if result["execution_success"]
                else "ERROR"
            ),
        )
        print(
            "  campos coinciden:",
            result["field_match"],
        )
        print(
            "  tiempo:",
            elapsed,
            "segundos",
        )

    durations = [
        result["duration_seconds"]
        for result in results
    ]
    successful_durations = [
        result["duration_seconds"]
        for result in results
        if result["execution_success"]
    ]
    ordered_successful_durations = sorted(
        successful_durations
    )

    if ordered_successful_durations:
        p95_index = max(
            ceil(
                0.95
                * len(
                    ordered_successful_durations
                )
            )
            - 1,
            0,
        )
        average_seconds = round(
            mean(successful_durations),
            3,
        )
        median_seconds = round(
            median(successful_durations),
            3,
        )
        p95_seconds = (
            ordered_successful_durations[
                p95_index
            ]
        )
    else:
        average_seconds = None
        median_seconds = None
        p95_seconds = None

    def count_check(field: str) -> int:
        return sum(
            result["checks"].get(field) is True
            for result in results
        )

    summary = {
        "cases": len(results),
        "successful_executions": sum(
            result["execution_success"]
            for result in results
        ),
        "execution_errors": sum(
            not result["execution_success"]
            for result in results
        ),
        "field_matches": sum(
            result["field_match"]
            for result in results
        ),
        "classification_matches": count_check(
            "classification"
        ),
        "status_matches": count_check(
            "analysis_status"
        ),
        "semantic_structure_valid": count_check(
            "semantic_structure"
        ),
        "expected_document_coverage_matches": (
            count_check(
                "expected_document_coverage"
            )
        ),
        "expected_document_coverage_evaluated": sum(
            result["checks"].get(
                "expected_document_coverage"
            )
            is not None
            for result in results
        ),
        "basis_structure_valid": count_check(
            "basis_structure"
        ),
        "total_seconds": round(
            sum(durations),
            3,
        ),
        "average_successful_seconds": (
            average_seconds
        ),
        "median_successful_seconds": (
            median_seconds
        ),
        "p95_successful_seconds": (
            p95_seconds
        ),
    }

    report = {
        "dataset_id": dataset["dataset_id"],
        "executed_at": (
            datetime.now(UTC).isoformat()
        ),
        "provider": "openrouter",
        "model": settings.openrouter_model,
        "metric_scope": (
            "Comparación automática de la "
            "clasificación y el estado esperados, "
            "estructura semántica de la valoración "
            "y coherencia de los fundamentos recuperados. "
            "La pertinencia y corrección jurídica "
            "requieren revisión manual."
        ),
        "summary": summary,
        "results": results,
    }

    RESULTS_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("RESUMEN")

    for key, value in summary.items():
        print(
            f"{key}: {value}"
        )

    print(
        "Resultados:",
        RESULTS_PATH,
    )


if __name__ == "__main__":
    main()
