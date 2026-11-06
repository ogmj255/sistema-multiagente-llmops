"""Exporta la referencia binaria y un manifiesto, SIN consultar modelos.

La referencia original V1 nunca se modifica. Los archivos generados
quedan en data/evaluation (gitignored) y NO se cargan en ChromaDB/RAG.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.evaluation.binary_groundtruth import (
    binary_manifest, load_binary_groundtruth_v2,
)
from app.evaluation.groundtruth import HEADERS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Proyección binaria NPA/PA del corpus congelado de 547 unidades."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/evaluation/v2_binary_ground_truth_547.csv"),
    )
    args = parser.parse_args()
    dataset = load_binary_groundtruth_v2(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.resolve() == args.csv.resolve():
        parser.error("El archivo V1 de origen no puede sobrescribirse.")

    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        for unit in dataset.units:
            writer.writerow({
                "ID técnico": unit.technical_id,
                "Plataforma": unit.platform,
                "Cláusula original completa": unit.original_text,
                "Aplicabilidad": unit.applicability,
                "Etiqueta final": unit.label,
            })
    manifest = binary_manifest(dataset)
    path = args.output.with_name("v2_binary_manifest.json")
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Referencia derivada: {args.output}")
    print(f"Manifiesto: {path}")
    print("Ningún texto o etiqueta original V1 fue modificado.")


if __name__ == "__main__":
    main()
