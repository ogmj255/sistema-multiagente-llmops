"""Preflight V2 seguro. NO realiza llamadas a OpenRouter ni cobra créditos.

Ejecutar dentro del servicio evaluation-worker con command override
(no inicia la cola ni el bucle de análisis).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.evaluation.readiness import (
    PreflightError,
    freeze_readiness,
    verify_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica el corpus V2, Chroma, Ollama y configuración."
    )
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("/app/data/evaluation"),
    )
    parser.add_argument(
        "--protocol", choices=("v2", "v3"), default="v2",
        help="Versión explícita; V3 no altera el preflight histórico V2.",
    )
    parser.add_argument(
        "--freeze", action="store_true",
        help="Crea manifiesto de reproducibilidad si no existe.",
    )
    args = parser.parse_args()

    try:
        if args.freeze:
            manifest = freeze_readiness(args.data_dir, version=args.protocol)
        else:
            _current = verify_readiness(args.data_dir, version=args.protocol)
            manifest = {
                "fingerprint": "manifiesto existente validado",
            }
    except (PreflightError, OSError, ValueError, KeyError) as exc:
        print(
            f"PRE-FLIGHT NO APROBADO: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            f"PRE-FLIGHT NO APROBADO: servicio local no disponible "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    print("PRE-FLIGHT APROBADO — no se invocó OpenRouter.")
    print(
        "Manifiesto:",
        args.data_dir / f"{args.protocol}_binary_preflight_manifest.json",
    )
    print("Huella:", manifest["fingerprint"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
