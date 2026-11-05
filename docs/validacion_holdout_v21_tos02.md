# Validación independiente del prompt V2.1: ToS02 OpenAI

**Fase:** validación previa a la campaña formal. La primera comparación en Holded, ET01-R1, mejoró de F1 macro 0,539642 a 0,583333 con el prompt V2.1, pero Holded se había inspeccionado para ajustar el prompt. No constituye validación independiente.

**Se pre-registra aquí una segunda comparación** sobre ToS02 OpenAI: 40 unidades contractuales, modelo DeepSeek T1, repetición R1 y tarea ET04-R1. La versión V2 se ejecuta en la rama histórica y V2.1 en la nueva rama de validación. Se juzgan ambas contra las mismas referencias humanas, sin enviarlas al LLM.

## Hipótesis y criterio de aceptación

Se considera prometedora la candidata V2.1 si simultáneamente:
- La mejora de F1 macro NPA/PA es igual o mayor a **+0,020000**.
- Los falsos negativos PA no aumentan.
- No se pierde ningún acierto de aplicabilidad respecto a V2.
- Las 40 unidades se clasifican válidamente en ambos brazos.
- Los contextos RAG son idénticos en ambas versiones, comprobados mediante SHA-256 por consulta distinta.

Se informarán también exactitud, matrices de confusión, diferencias por ID técnico, duración, costos reportados y prueba exacta de McNemar. El resultado sobre un solo documento **no demuestra superioridad global** ni generalización a Mistral o Kimi. No modificar estas reglas después de ver el resultado.

## Almacenamiento aislado

Se conservan sin modificación los archivos históricos de V2, el piloto V2.1 de Holded y sus manifiestos. Los únicos datos nuevos se crean en:

data/evaluation/v21_holdout_tos02/

Dentro de esa carpeta estarán:

- preflight_manifest.json: criterios y huellas pre-registrados;
- v2_baseline/runs.jsonl y v2_baseline/unit_checkpoints.jsonl;
- v2_baseline/legal_context_snapshots.jsonl;
- v21_candidate/runs.jsonl y v21_candidate/unit_checkpoints.jsonl;
- v21_candidate/legal_context_snapshots.jsonl;
- comparison.json: informe apareado sin gasto adicional.

**No reutilizar predicciones ni checkpoints entre V2 y V2.1**. El RAG debe ofrecer el mismo contenido de respaldo para ambas condiciones.

## Fase A — Preparación y congelación, sin gasto

Primero comprobar en la aplicación que no hay tareas en cola o ejecución. En el archivo .env principal dejar EXPERIMENT_EXECUTION_ENABLED=false. Detener el worker V2 únicamente después de confirmar que está inactivo:

~~~powershell
docker compose --profile experiment stop evaluation-worker
git status --short
git fetch origin
git switch --track origin/experiment/v21-holdout-validation

$env:PYTHONPATH = (Resolve-Path ".\backend").Path

python -m pytest tests/unit/test_v21_holdout.py tests/unit/test_v21_prompt_semantics.py tests/unit/test_prompt_v21_validation_runner.py -q
python -m pytest tests/unit -q
docker compose --profile experiment config --quiet
~~~

Si la rama ya está creada en el equipo, utilizar git switch experiment/v21-holdout-validation en vez de git switch --track.

No borrar ni ocultar mediante limpieza destructiva los datos locales. Si aparecen conflictos de Git, detener el procedimiento antes de modificar archivos.

Tras aprobar las pruebas, congelar el holdout **sin inferencia**:

~~~powershell
docker compose --profile experiment build evaluation-worker
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_v21_holdout --freeze
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_v21_holdout --verify
~~~

Se espera HOLDOUT CONGELADO y HOLDOUT VERIFICADO con la misma huella nueva. No se modifica el manifiesto V2 ni el preflight del piloto V2.1 original.

## Fase B — Baseline V2, una tarea pagada

**No ejecutar sin comprobar saldo, estado del worker y autorizar el costo.** El límite de USD 0,10 es blando, no un máximo de facturación. El backend/Streamlit deben quedar sin solicitudes de evaluación mientras se alternan las ramas.

Desde la rama histórica original y con el worker normal detenido:

~~~powershell
git switch experiment/binary-classification-ui-v2
docker compose --profile experiment build evaluation-worker
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.preflight_binary_worker

docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.run_groundtruth_campaign --csv data/evaluation/ground_truth_547.csv --task-id ET04-R1 --max-tasks 1 --execute --confirm-full-document --max-reported-cost-usd 0.10 --output data/evaluation/v21_holdout_tos02/v2_baseline/runs.jsonl --context-cache data/evaluation/v21_holdout_tos02/v2_baseline/legal_context_snapshots.jsonl --unit-checkpoints data/evaluation/v21_holdout_tos02/v2_baseline/unit_checkpoints.jsonl
~~~

Estos comandos ejecutan una única tarea de 40 cláusulas por LangGraph/MCP, no 90. Si hay un error o ejecución incompleta, preservar los resultados y no repetir sin auditar el gasto.

## Fase C — Candidata V2.1, una tarea pagada

Solo después de comprobar que la V2 ha producido un resultado completo de 40 unidades, regresar a la rama holdout:

~~~powershell
git switch experiment/v21-holdout-validation
docker compose --profile experiment build evaluation-worker
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_v21_holdout --verify
~~~

Con el worker normal detenido, EXPERIMENT_EXECUTION_ENABLED=false y saldo/compras autorizados:

~~~powershell
docker compose --profile experiment run --rm --no-deps -e V21_HOLDOUT_EXECUTION_ENABLED=true evaluation-worker python -m scripts.validate_v21_holdout --execute-candidate --confirm-paid-run --max-reported-cost-usd 0.10
~~~

El programa exige manifiesto válido, ejecución V2 única y completa, ausencia de trabajos normales activos y rutas candidatas libres. Usa el LangGraph/MCP/RAG/OpenRouter reales. No dispara ninguna tarea adicional.

## Fase D — Comparación sin gasto

Después de ejecutar ambas condiciones completas:

~~~powershell
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_v21_holdout --compare
~~~

El programa guarda comparison.json con métricas, diferencias por unidad, prueba apareada, aciertos de aplicabilidad, equivalencia RAG y aceptación/rechazo del criterio pre-registrado.

## Decisión posterior

Si falla el criterio, documentar que el piloto Holded fue favorable pero la validación en ToS02 no confirmó la mejora. Si se cumple, la candidata cuenta con una señal de robustez adicional; validar trazas/costos y después proponer el protocolo de **una campaña formal nueva V2.1 de 90 tareas**, con directorios propios. No mezclar pilotos V2/V2.1 en las repeticiones formales ni presentar una muestra única como prueba concluyente.
