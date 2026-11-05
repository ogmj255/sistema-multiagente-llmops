"""Valida el anexo y calcula métricas de predicciones JSONL."""

import argparse
import json
from pathlib import Path

from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.metrics import read_predictions, score_predictions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluación controlada del ground truth SaaS."
    )
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    groundtruth = load_groundtruth_csv(args.csv)
    report: dict[str, object] = {
        "groundtruth": groundtruth.manifest(),
    }
    if args.predictions:
        if not args.model:
            parser.error("--model es obligatorio con --predictions.")
        report["evaluation"] = score_predictions(
            groundtruth,
            read_predictions(args.predictions),
            model=args.model,
        )
    elif args.model or args.output:
        parser.error("--model y --output requieren --predictions.")

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
