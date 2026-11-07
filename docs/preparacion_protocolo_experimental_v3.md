# Preparación del protocolo binario V3 — 547 unidades (6/11/2026)

**Estado:** cambios de código disponibles en rama aislada; **NO ejecutar 90 tareas** hasta completar verificación en el equipo del investigador, decidir el prompt y congelar el preflight V3. No se han ejecutado llamadas a OpenRouter por estos cambios.

## Procedencia y alcance

Referencia aprobada por el investigador: ANEXO-GroundTruth_FINAL_corregido_20261106.xlsx (hoja «Ground truth»). Debe usarse **exactamente** el CSV preparado y no rehacer el archivo en Excel/Windows, porque el SHA del archivo se verifica byte a byte.

- Filas: 547; 10 ToS; todos los IDs y textos originales conservan orden e integridad del CSV histórico.
- Clasificación: **NPA 318 / PA 156** sobre **474 unidades evaluables**.
- Estado ajeno a clasificación binaria: **73 not_applicable**.
- Cambios de referencia respecto al CSV histórico proyectado a PA/NPA: **7**.
- Se respetan ToS02-U023=not_applicable, ToS05-U001=NPA y ToS05-U002=PA.
- Encabezado CSV: ID técnico | Plataforma | Cláusula original completa | Aplicabilidad | Etiqueta final.

### Huellas

| Concepto | SHA-256 |
| --- | --- |
| CSV V3 exacto | b729651c57a80d6622ad8a5722b3a2fe369842e4c147c988a45a0a6b83215eb0 |
| Huella fuente V1 estilo (V3) | c59cb35c732d5c51041c22f5c47d923b077a32b9bd2d46e42124ca6fe8275943 |
| Huella binaria V3 | 8dc8ad7b83bd2985eeebcdac7ab55c44580d36ff279844bd818a9bed8a10cd5c |
| Huella V2 histórica (NO reutilizar) | d1e589a83a2019cde901c61f7a1f850815642431701e19b5f349d90b57a13a84 |

El CSV **no está en Git**; conservarlo exclusivamente en la carpeta local gitignored data/evaluation/. El código del repositorio contiene hashes y conteos, no las etiquetas individuales ni textos del dataset.

## Cambios de código versionados en la rama

- evaluation/binary_groundtruth.py: **opt-in V3** con huellas fuente, bytes, texto e integridad de 547 unidades.
- evaluation/readiness.py: manifiesto preflight V3 independiente del manifiesto histórico V2. Bloquea cambios de RAG, configuración, código, modelos y dataset.
- scripts/preflight_binary_worker.py: opción --protocol v3.
- scripts/run_groundtruth_campaign.py: opción --protocol v3, rutas V3 separadas y comprobación preflight obligatoria antes de pagar.
- scripts/score_groundtruth_campaign.py: puntúa V3 separadamente, sin cargar V2.
- scripts/verify_groundtruth_v3.py: validación **local y gratuita**, sin Ollama, OpenRouter ni MCP.
- tests/unit/test_binary_protocol_v3.py y test_campaign_v3_cli.py: regresión para hashes y aislamiento.

### Bloqueador de decisión: versión del prompt

La rama procede de experiment/v21-holdout-validation y, por tanto, **hereda el prompt candidato V2.1**. V2.1 no superó el holdout ET04-R1. **No confundir «V3» (versión del ground truth) con la versión del prompt.** Antes de congelar el preflight definitivo hay que seleccionar explícitamente el prompt y registrar esa selección; la sugerencia preliminar es emplear V2 como referencia original, conservando los resultados exploratorios previos. No continuar a ejecución pagada por el solo hecho de que se obtenga un preflight técnico V3 válido.

### Bloqueo obligatorio de aprobación de prompt

El preflight V3 **se negará a congelar** hasta que exista el archivo
privado gitignored data/evaluation/v3_final_prompt_selection.json. Debe
crearse **solo después** de seleccionar la versión definitiva y verificar
que el código real coincida con esa versión. Ejemplo de estructura
(no copiar todavía como si hubiera aprobación):

~~~json
{
  "prompt_version": "V2",
  "prompt_source_sha256": "SHA256_REAL_DEL_ARCHIVO_SELECCIONADO",
  "approved_by": "investigador responsable",
  "approved_at": "FECHA_ISO_8601",
  "selection_rationale": "Justificación metodológica de elección del prompt."
}
~~~

El validador coteja SHA-256 y además la identidad Git exacta de los
prompts históricos **V2** (blob
591b13b8a663c83891812ea6deebaf1ceb4685bd) y **V2.1**
(blob 5be7988b570bef4f72365f6c9b2d1f2f8a0ce9fb).
Por tanto, **no es posible declarar que el código V2.1 es V2** para
superar el bloqueo. En esta rama el prompt sigue siendo V2.1, por lo
que la selección V2 requiere restaurar el archivo correspondiente
desde experiment/binary-classification-ui-v2 ANTES de crear la aprobación
y de congelar el preflight. No modificar el prompt tras congelarlo.

## Instalación segura: PowerShell en la raíz del proyecto

1. Respaldar cambios locales y cambiar a la rama V3. No hacer un git reset que descarte trabajo.

    git status --short
    git fetch origin
    git switch --track origin/experiment/groundtruth-v3-final

2. Colocar el CSV descargado del chat, **sin abrirlo ni reexportarlo en Excel**, en:

    data/evaluation/ground_truth_547_v3.csv

3. Verificar la copia y los tests **sin llamadas pagadas**:

    (Get-FileHash .\data\evaluation\ground_truth_547_v3.csv -Algorithm SHA256).Hash.ToLower()
    $env:PYTHONPATH = (Resolve-Path ".\backend").Path
    python -m pytest tests/unit/test_binary_protocol_v3.py tests/unit/test_campaign_v3_cli.py tests/unit/test_binary_protocol_v2.py tests/unit/test_groundtruth_evaluation.py -q
    python -m scripts.verify_groundtruth_v3 --csv data/evaluation/ground_truth_547_v3.csv
    python -m scripts.run_groundtruth_campaign --csv data/evaluation/ground_truth_547_v3.csv --protocol v3 --task-id ET01-R1

La última orden es una **vista previa**, no lleva --execute y no llama OpenRouter.

4. Tras seleccionar y congelar el prompt final, construir el worker e iniciar/verificar el preflight V3 en modo lectura:

    docker compose --profile experiment build evaluation-worker
    docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.preflight_binary_worker --protocol v3 --freeze
    docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.preflight_binary_worker --protocol v3

Estos pasos requieren acceso a ChromaDB, Ollama, claves configuradas y Langfuse, pero **no realizan llamadas de inferencia a OpenRouter**. El preflight bloquea cualquier modificación posterior del código, prompt, dataset o base jurídica.

La campaña de 90 tareas solo debe iniciarse tras revisión del preflight, presupuesto, ausencia de workers simultáneos, compatibilidad real de DeepSeek/Mistral/Kimi y prueba técnica controlada de formato JSON.

### Identificadores y archivos de la campaña V3

- dataset: data/evaluation/ground_truth_547_v3.csv
- preflight: data/evaluation/v3_binary_preflight_manifest.json
- resultados: data/evaluation/v3_binary_campaign_runs.jsonl
- RAG congelado: data/evaluation/v3_binary_legal_context_snapshots.jsonl
- checkpoints: data/evaluation/v3_binary_unit_checkpoints.jsonl
- métricas: data/evaluation/v3_binary_metrics_by_repetition.json / .csv y v3_binary_metrics_by_document.csv / .json.

**Precaución:** la interfaz y el worker persistente evaluation_worker.py están aún ligados a V2. La vía preparada para V3 es la CLI documentada, que llama al LangGraph/MCP real. No activar la interfaz/worker V2 para intentar ejecutar tareas V3. Las pruebas de principio a fin desde URL deben mantenerse como evaluación funcional separada, porque esta campaña inyecta cláusulas congeladas.

La ejecución con costo requerirá --protocol v3, --execute, --confirm-full-document y --max-reported-cost-usd, más el preflight validado. El límite de costos es **blando**, no una garantía de facturación máxima; la conciliación con Langfuse/OpenRouter es posterior.

## Revisión humana y ética de investigación

- La V3 se prepara por decisiones humanas previas; no se usaron las predicciones de los modelos para seleccionar automáticamente nuevas etiquetas.
- El registro de siete diferencias es una *traza de cambios*, no prueba de consenso humano interanotador ni justificación jurídica completa.
- Los pilotos V2/V2.1 y sus huellas no se recalculan retrospectivamente como si hubieran utilizado la referencia V3.
- No cargar los textos etiquetados en RAG ni subir el ground truth al repositorio.
- La evaluación principal se basará en PA/NPA sobre evaluables; el reconocimiento de no aplicables se reportará como diagnóstico separado.
