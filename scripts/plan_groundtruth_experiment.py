"""Genera el plan experimental definido en la tesis, sin invocar LLM."""

import argparse
import json
from pathlib import Path

from app.evaluation.design import make_experimental_plan
from app.evaluation.groundtruth import load_groundtruth_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/evaluation/plan_90_ejecuciones.json"),
    )
    args = parser.parse_args()

    groundtruth = load_groundtruth_csv(args.csv)
    plan = make_experimental_plan(groundtruth)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Plan generado: {plan['combinations']} combinaciones, "
        f"{plan['executions']} ejecuciones, "
        f"{plan['expected_unit_predictions']} predicciones previstas."
    )
    print(f"Salida: {args.output}")


if __name__ == "__main__":
    main()
