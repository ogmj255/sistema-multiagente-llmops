# Preparación del protocolo binario V3 — 547 unidades (6/11/2026)

**Estado actualizado:** ground truth V3 validado localmente; **V2 seleccionado como prompt definitivo**, restaurado en esta rama y aprobado por el investigador el 6/11/2026 a las 21:19:50 -05:00. Las 23 pruebas unitarias disponibles aprobaron tras seleccionar el prompt V2. Se agregó posteriormente una regresión de portabilidad SHA LF/CRLF, cuya ejecución local aún debe verificarse. Falta congelar y revalidar el preflight de infraestructura. **No ejecutar la campaña formal ni inferencias pagadas antes de completar los controles.**

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

### Decisión metodológica: prompt V2 seleccionado (6/11/2026)

El investigador confirmó la selección del **prompt V2** para la campaña definitiva V3. Se restauró el archivo completo `backend/app/prompts/legal_analysis.py` desde la rama histórica `experiment/binary-classification-ui-v2`, con identidad Git exacta `591b13b8a663c83891812ea6deebaf1ceb4685bd`.

**Justificación:** V2.1 fue un ajuste exploratorio que no cumplió el criterio de aceptación preestablecido en el contraste ET04-R1 (OpenAI, 37 unidades evaluables). Frente a V2, V2.1 presentó F1 macro 0,559562 vs. 0,571195 y exactitud 0,567568 vs. 0,594595, aunque mejoró el recall PA. Esta comparación no demuestra superioridad estadística universal de V2. Seleccionar el prompt de referencia anterior al ajuste evita adoptar como definitivo un cambio que no superó su validación. Los ensayos previos se conservan como evidencia exploratoria, sin reetiquetar sus resultados históricos.

**Distinción esencial:** V2 designa el **prompt** y V3 la **versión del ground truth/protocolo**. La selección se aprobó en el entorno Windows del investigador y la comprobación `_approved_v3_prompt` retornó la huella SHA-256 `f2176fa6d56de490395a21fd8fd82448e3a7d8697bfe405885508c56bb094bdd`. El registro privado `v3_final_prompt_selection.json` permanece en el equipo del investigador. La referencia del corpus no se modificó. Pendiente: verificación del mismo registro dentro de Docker y preflight.

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
Por tanto, **no es posible declarar que el código V2.1 es V2** para superar el bloqueo. El prompt V2 original **ya está restaurado** en la rama V3; el validador reconoce checkout LF/CRLF para la identidad Git, pero exige el SHA-256 de los bytes exactos del archivo aprobado. No modificar el prompt después de aprobarlo o congelar el preflight.

### Registro local de la aprobación (PowerShell, sin OpenRouter)

Una vez actualizado el repositorio y repetidas las pruebas con el prompt V2, crear el registro privado **en el equipo del investigador**, a partir del archivo real. Este ejemplo evita el BOM UTF-8 de Windows PowerShell 5.1:

~~~powershell
$promptPath = ".\\backend\\app\\prompts\\legal_analysis.py"
$approvalPath = Join-Path (Resolve-Path ".\\data\\evaluation").Path "v3_final_prompt_selection.json"
$approval = [ordered]@{
    prompt_version = "V2"
    prompt_source_sha256 = (Get-FileHash $promptPath -Algorithm SHA256).Hash.ToLower()
    approved_by = "Investigador responsable"
    approved_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz")
    selection_rationale = "Se adopta V2 como prompt de referencia previo al ajuste V2.1; V2.1 no cumplio el criterio de aceptacion en ET04-R1. La comparacion exploratoria no demuestra superioridad estadistica universal de V2."
}
$json = $approval | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($approvalPath, $json, [System.Text.UTF8Encoding]::new($false))
~~~

La fecha registrada debe ser la real del acto de aprobación; no atribuir verificaciones aún no ejecutadas. El JSON permanece bajo `data/evaluation/` (gitignored) y **no se sube a GitHub**. El preflight coteja obligatoriamente la identidad exacta Git del prompt V2/V2.1 y acepta el SHA-256 del mismo contenido en LF o CRLF, para admitir checkouts Windows/Docker sin pedir una nueva aprobación. **No acepta modificaciones textuales, cambios de versión o una huella inventada**. No alterar el prompt aprobado, desactivar la validación ni sustituir hashes a mano.

### Portabilidad del preflight (Windows y Docker)

La aprobación del 6/11/2026 se creó en PowerShell y se verificó con el prompt V2 local. El preflight usa el mismo archivo de aprobación en la carpeta montada `data/evaluation` y admite exclusivamente los saltos LF/CRLF del mismo blob Git oficial. La función de inventario del código también busca `repo/scripts` en un checkout y `/app/scripts` dentro del contenedor. Se añadieron pruebas específicas para ambas condiciones; requieren ejecución local posterior a esta actualización. **No sustituir el JSON existente ni volver a aprobar el prompt por una diferencia de plataforma.**

Antes de congelar el preflight, comprobar la aprobación en el worker Docker, sin ejecutar la cola V2 ni la campaña:

~~~powershell
docker compose --profile experiment build evaluation-worker
docker compose --profile experiment run --rm --no-deps evaluation-worker python -c "from pathlib import Path; from app.evaluation.readiness import _approved_v3_prompt; print(_approved_v3_prompt(Path('/app/data/evaluation')))"
~~~

Esto verifica que el volumen privado está montado y que la misma identidad V2 se valida desde Linux. Solo después de confirmar Docker, Chroma, Ollama y Langfuse realizar el preflight `--freeze` indicado más abajo.

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
