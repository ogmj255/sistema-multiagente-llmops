# Evaluación experimental — capítulo III, sección 3.7

Esta rama contiene validación del ground truth, métricas, plan experimental,
un piloto aislado y un **piloto multiagente vía LangGraph + MCP**. El flujo integrado ya se verificó en el equipo del investigador mediante
LangGraph/MCP/OpenRouter/Langfuse con T1, T2 y T3 (unidad ToS01-U001).
El nuevo ejecutor de campaña documental superó 17 pruebas en VS Code
(el 04/11/2026); el checkpoint por unidad y el evaluador por repetición
se añadieron posteriormente y todavía requieren pruebas.

## Referencia humana

La fuente es `ANEXO-GroundTruth.xlsx`, hoja única, exportada localmente a
`data/evaluation/ground_truth_547.csv` (UTF-8 y cabeceras originales).
Esta ruta está excluida de Git. **No subir el CSV etiquetado al RAG ni al
repositorio**. La decisión final del investigador para `ToS05-U002` es
`no potencialmente abusiva`; conservar como evidencia la captura de
validación y la huella del dataset.

La versión validada en el equipo del investigador contiene 547 unidades,
10 ToS y el fingerprint:

`47f69eb943f539751f2c120ab6fdd7f45bbc000f93459a90f1162212cfdde4a5`

La huella se comprueba otra vez antes de cualquier inferencia.

## Diseño fijado en la tesis

- **Factor variable:** modelo LLM.
- **Tratamientos:** T1 DeepSeek V4 Flash 0731, T2 Mistral Large 3 2512,
  T3 Kimi K2.6, todos previstos a través de OpenRouter.
- **Objetos:** 10 documentos ToS SaaS; **unidades:** 547 fragmentos fijos.
- **Diseño:** 30 combinaciones documento-modelo (ET01–ET30);
  3 repeticiones por combinación; 90 ejecuciones documentales y
  4.923 predicciones individuales previstas.
- **Constantes:** mismo fragmento y orden, prompt, modelo de embeddings,
  corpus jurídico, configuración de recuperación semántica y entorno.
- **Indicadores:** precisión, recall, F1, exactitud, latencia de extremo a
  extremo, tokens, costo y tasa de error.

Los identificadores API escritos en `backend/app/evaluation/design.py`
corresponden a los tres modelos listados actualmente en OpenRouter.
La accesibilidad real con la clave del investigador y la compatibilidad
con el esquema JSON deben comprobarse en el piloto. Se registra el
modelo efectivamente devuelto y se congelan las versiones antes de ejecutar. Los nombres académicos de la tesis
son la referencia autoritativa hasta esa verificación.

## Uso en VS Code (PowerShell, desde la raíz)

```powershell
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_groundtruth_evaluation.py tests/unit/test_experiment_design.py -q
python scripts/evaluate_groundtruth.py --csv data/evaluation/ground_truth_547.csv
python scripts/plan_groundtruth_experiment.py --csv data/evaluation/ground_truth_547.csv
```

El último comando crea `data/evaluation/plan_90_ejecuciones.json`
(excluido de Git) y **no realiza llamadas a modelos**.

## Piloto técnico (máximo cinco unidades por orden)

Antes de usar `--execute`, configurar localmente
`OPENROUTER_API_KEY` en `backend/.env`, iniciar Ollama para embeddings,
ChromaDB con el corpus jurídico indexado y verificar conectividad. No
introducir credenciales en comandos, GitHub ni documentos académicos.
El archivo etiquetado no se envía al LLM.

Desde la raíz del repositorio en **PowerShell**:

```powershell
git pull --ff-only origin experiment/groundtruth-evaluation
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_groundtruth_evaluation.py tests/unit/test_experiment_design.py tests/unit/test_experimental_pilot.py tests/unit/test_experimental_model_selection.py -q

# Vista previa (ninguna consulta RAG/API y ningún costo)
python scripts/run_experimental_pilot.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R1 --unit-id ToS01-U001

# Solo tras verificar los servicios y la API: una inferencia real
python scripts/run_experimental_pilot.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R1 --unit-id ToS01-U001 --execute
```

Para comparar exactamente **la misma unidad** en los otros tratamientos,
cambiar `ET01-R1` por `ET02-R1` y `ET03-R1` y conservar
`--unit-id ToS01-U001`. Esto genera tres inferencias de piloto que
comparten la misma instantánea jurídica. No son aún la evaluación completa.

**Archivos locales excluidos de Git**:

- `data/evaluation/pilot_predictions.jsonl`: predicción, respuesta
  estructurada, modelo solicitado/real, tiempo, tokens, costo, error, ID de
  traza, hashes de prompt y contexto. No contiene etiqueta humana.
- `data/evaluation/legal_context_snapshots.jsonl`: resultados del agente de
  conocimiento congelados por ID, hash del fragmento y configuración RAG.

`--execute` puede consumir créditos de OpenRouter; sin él, la orden es
solo una vista previa. Un fallo de RAG se registra y **no dispara llamadas
al modelo con contexto vacío**. Si un intento falla, solo se reintenta
expresamente con `--retry-errors`. Una ejecución con éxito no se repite
accidentalmente.

**Limitación académica:** este piloto mide latencia de inferencia y de
recuperación jurídica por separado, no la latencia extremo a extremo de la
aplicación completa. El evaluador de predicciones `JSONL` disponible
actualmente consolida una predicción por ID y modelo: **todavía no es
adecuado para evaluar las tres repeticiones** de la fase formal.

## Integración del sistema multiagente real (preferida)

**Ruta nueva:** `scripts/run_orchestrated_experiment.py`.

Esta ejecución utiliza el **grafo real `AgenteOrquestador` de LangGraph**
y los nodos `procesar_clausula`, `generar_informe` y
`finalizar_flujo` del código productivo. Los nodos de entrada inyectan
los textos congelados del ground truth; **no vuelven a realizar extracción
web ni segmentación**, ya que eso modificaría las unidades experimentales.
Las operaciones jurídicas, de análisis, generación de informe y
observabilidad se invocan por los servidores **MCP stdio reales**.

La selección T1/T2/T3 se transmite únicamente a la variable
`OPENROUTER_MODEL` del proceso MCP del analizador, sin alterar el modelo
global de producción. La primera recuperación jurídica de un fragmento
se obtiene a través de MCP y se guarda como instantánea en
`data/evaluation/mcp_legal_context_snapshots.jsonl`; los demás
tratamientos usan **exactamente el mismo contexto recuperado**.
Se registran ID de tarea, modelo, repetición, predicción, reporte, resumen
operativo y referencia de ejecución en Langfuse.

Desde VS Code en PowerShell (raíz del proyecto):

```powershell
git pull --ff-only origin experiment/groundtruth-evaluation
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_orchestrated_experiment.py -q

# Vista previa del sistema integrado; sin facturación ni servidores MCP
python scripts/run_orchestrated_experiment.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R1 --unit-id ToS01-U001

# SOLO tras validar las pruebas, infraestructura y saldo:
python scripts/run_orchestrated_experiment.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R1 --unit-id ToS01-U001 --execute
```

Para comprobar los otros dos tratamientos sobre el **mismo** fragmento,
ejecutar después ET02-R1 y ET03-R1. La primera corrida recupera RAG
con MCP; las siguientes reutilizan la instantánea. Cada corrida genera
un informe por el servidor MCP de reportes y un resumen de observabilidad.

Los registros se guardan en
`data/evaluation/orchestrated_runs.jsonl`, excluido de Git.
No almacenan etiquetas humanas. Una repetición correcta no se vuelve a
ejecutar accidentalmente. La ejecución se limita actualmente a **una
unidad por comando**, para evitar facturación masiva sin verificación.

**Delimitación:** esta es la evaluación controlada de clasificación con
arquitectura multiagente. La **evaluación de extremo a extremo desde URL**
se hará por separado mediante el flujo normal `/analisis` (Web Scraper y
Preprocesador incluidos). La variante controlada no inserta resultados en
PostgreSQL productivo; conserva resultados en JSONL y trazas mediante la
instrumentación existente de Langfuse. Antes de la evaluación completa
faltan el ejecutor de 90 tareas, la persistencia experimental dedicada y
las métricas separadas por repetición. No atribuir al piloto el rendimiento
de la aplicación completa.

El script anterior `run_experimental_pilot.py` sigue disponible como
**prueba aislada**, pero no representa el flujo multiagente integrado y
no debe usarse para la evaluación formal del capítulo IV.

## Política de recuperación ante HTTP 429

El cliente **OpenRouter real** aplica esta política para todos los modelos
sin cambiar el tratamiento solicitado:

- Máximo **3 solicitudes HTTP** por inferencia cuando el proveedor devuelve
  un 429; las esperas sin encabezado son de **2 y 4 segundos** (exponenciales).
- Si existe `Retry-After`, respeta su valor en segundos o fecha HTTP. Si la
  espera indicada supera el máximo configurado (30 segundos por defecto),
  **termina y registra el bloqueo**, sin reintentar antes del plazo requerido.
- Los errores HTTP diferentes de 429 (incluidos 401 y 402) **no se reintentan
  automáticamente**. Tampoco se repiten ciegamente los errores de conexión,
  para evitar dobles cobros cuando se desconoce si la generación ocurrió.
- Cada intento HTTP cuenta con su propia generación/error en Langfuse; si
  finalmente hay éxito, `request_attempts` y `http_429_count` se incorporan
  a la telemetría MCP de la clasificación.
- Cuando se agotan intentos ante 429, la respuesta MCP lleva el código
  `provider_rate_limited`. El orquestador **no realiza otros dos intentos
  externos**; el error conserva el número de intentos del cliente OpenRouter.
  El campo `attempt` del fallo LangGraph indica **invocaciones MCP**, no
  solicitudes HTTP internas.
- Los fallos de proveedor son **operativos**; no se convierten en etiquetas
  falsas ni se incluyen como clasificaciones erróneas.

Configuración en `backend/.env` si se requiere personalizar:

```env
OPENROUTER_RETRY_MAX_ATTEMPTS=3
OPENROUTER_RETRY_INITIAL_DELAY_SECONDS=2.0
OPENROUTER_RETRY_MAX_DELAY_SECONDS=30.0
```

Pruebas nuevas (sin consumir API):

```powershell
python -m pytest tests/unit/test_openrouter_retry_policy.py tests/unit/test_llm_clients.py tests/unit/test_orchestrated_experiment.py tests/unit/test_mcp_registry.py -q
```

**Mistral ET02-R1** registró un fallo inicial HTTP 429 y posteriormente
clasificó ToS01-U001 con éxito en un segundo intento de ejecución (con
2 solicitudes HTTP internas y 1 respuesta HTTP 429). Ambos registros se
conservan en `orchestrated_runs.jsonl`. El piloto no se fusiona
con los resultados formales y no se reescriben los errores anteriores.
Las pruebas de la política de recuperación pasaron: 27 tests en VS Code
el 04/11/2026.

## Campaña formal por documento (nueva, pruebas pendientes)

Comando: `scripts/run_groundtruth_campaign.py`. Este ejecutor
**no llama directamente al LLM**: llama a `run_orchestrated_trial`,
que reutiliza el grafo LangGraph y los servidores MCP de producción.

Cada tarea `ETxx-Rn` agrupa **todas** las unidades del ToS y genera
un informe documental; así se preservan 30 combinaciones y 3 repeticiones
por combinación (90 ejecuciones documentales en total).

- Inicia con **vista previa**, sin conexiones MCP ni facturación.
- Valida huella del ground truth y correspondencia exacta entre ToS,
  modelo y unidades congeladas.
- Conserva intentos previos en `data/evaluation/formal_campaign_runs.jsonl`
  y omite solamente tareas con **todas** sus unidades clasificadas y
  un informe completo. Un fallo requiere `--retry-errors` para repetir
  el documento, y no se borra su registro.
- El contexto jurídico formal se guarda aparte, en
  `data/evaluation/formal_legal_context_snapshots.jsonl`, para no
  reutilizar datos del piloto técnico. Se comparte entre tratamientos
  manteniendo la misma configuración RAG.
- Solo permite **1–5 tareas documentales por comando** (`--max-tasks`;
  valor predeterminado 1) y bloquea simultaneidad sobre el mismo JSONL.
- Una solicitud real requiere **tres elementos explícitos**:
  `--execute --confirm-full-document --max-reported-cost-usd N`.
  **N es un límite blando del costo informado en esa invocación**:
  se comprueba *después* de cada tarea y antes de iniciar otra. No
  puede cortar una tarea ya iniciada y NO garantiza un tope de
  facturación, especialmente cuando faltan datos de uso en fallos.
  Verificar saldo disponible y costos de los modelos antes de habilitarlo.
- Nunca usa las etiquetas humanas en el prompt. Las predicciones
  permanecen separadas del ground truth; el cálculo de precisión/recall/F1
  se hará después con denominador fijo y agrupación por repetición.

### Instrucciones inmediatas en VS Code (sin consumo)

```powershell
git pull --ff-only origin experiment/groundtruth-evaluation
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_experimental_campaign.py tests/unit/test_experiment_design.py tests/unit/test_orchestrated_experiment.py tests/unit/test_openrouter_retry_policy.py -q
python scripts/run_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R2
```

La última orden solo debe mostrar el estado y la vista previa de ET01-R2;
no ejecutar con `--execute` hasta verificar los resultados y
acordar una política de costos y manejo de ejecuciones incompletas.

## Checkpoint por unidad y métricas por repetición (nuevo, pendiente de pruebas)

El ejecutor formal ahora entrega `--unit-checkpoints` a
`run_orchestrated_trial`. El procesamiento se mantiene en **LangGraph**
con los servidores **MCP de conocimiento, análisis, informes y
observabilidad**. Cada nodo de cláusula guarda su resultado y telemetría
inmediatamente en `data/evaluation/formal_unit_checkpoints.jsonl`
mediante `flush` + `fsync`, sin incluir ninguna etiqueta humana.

Al reanudar la misma tarea, se verifica estrictamente el ID, huella
del dataset, SHA del texto, modelo, repetición y huella de configuración
(prompt, esquema, temperatura, embeddings y colección). Solo se omiten
las unidades **exitosas**; los fallos siguen pendientes. La reanudación
reconstruye el informe del documento por el agente generador MCP. El
informe identifica los resultados reutilizados y los nuevos. El costo
reportado de las unidades recuperadas está disponible por separado en
`checkpoint.cumulative_success_usage`: no debe sumarse dos veces al
costo de la nueva ejecución. No existe garantía de "exactly once" si
se interrumpe una solicitud antes del guardado; podría haberse facturado.

El script `scripts/score_groundtruth_campaign.py` evalúa los resultados
**después** del procesamiento, sin invocar OpenRouter. Produce JSON con
matrices de confusión y métricas de las **cuatro clases** (incluida N/A)
y de las **tres categorías evaluables**, separadas por T1/T2/T3 y
R1/R2/R3; genera un CSV con nueve filas resumen. Conserva 547 como
denominador por modelo/repetición y muestra cobertura, unidades sin
predicción y errores operativos sin atribuirles una categoría jurídica.
El promedio de F1 de un tratamiento solo se presenta cuando sus tres
repeticiones están completas.

### Validación sin consumo de créditos

```powershell
git pull --ff-only origin experiment/groundtruth-evaluation
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_experimental_campaign.py tests/unit/test_unit_checkpoint.py tests/unit/test_orchestrated_experiment.py tests/unit/test_repetition_metrics.py -q
python scripts/run_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv --task-id ET01-R2
python scripts/score_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv
```

El último comando produce métricas **provisionales con cobertura cero**
mientras no existan tareas formales. No representa un resultado
de clasificación y no consume créditos.

**Condiciones pendientes antes de lanzar el corpus completo:** confirmar
checkpoint en VS Code mediante pytest; auditar huella/versionado de la
base jurídica ChromaDB y versiones del código y modelos; comprobar
presupuesto y límites; ejecutar un documento completo como piloto formal
con gasto controlado; revisar trazabilidad por unidad y validez de los
denominadores. **No ejecutar las 90 tareas todavía.**



## Lectura correcta del primer resultado documental (ET01-R1)

Ejecución real de Holded con DeepSeek, 21 unidades: **21/21 predicciones
registradas, 7 coincidencias con el ground truth y 14 desacuerdos**.
Exactitud **documental**: 7/21 = 33,33%. La duración reportada es
1.301.697,229 ms (~21 min 42 s) y el costo total reportado de la tarea
es USD 0,0215251.

El primer CSV de las nueve celdas presentó una exactitud de 0,012797 y
F1 macro de 0,015841 para T1-R1 porque esos cálculos tienen como
denominador **las 547 unidades del corpus**, aunque las 526 restantes
están sin ejecutar. Son **métricas ajustadas por cobertura**, no la
calidad de DeepSeek sobre el documento Holded ni su tasa de error
operativo. No usar esos valores como resultado final del capítulo IV.

La matriz de confusión de Holded indica que DeepSeek asignó siete veces
`indicios fuertes de abusividad` sin que esa clase estuviera presente
entre las etiquetas humanas de ese documento. Evaluar
cualitativamente esos desacuerdos antes de inferir tendencias
de rendimiento o modificar prompts.

### Corrección del evaluador (pendiente de pruebas en VS Code)

- `backend/app/evaluation/document_metrics.py` calcula métricas
  independientes para cada una de las 90 tareas: precisión documental,
  F1 macro, matriz de confusión y subconjunto evaluable. Solo marca
  una calidad definitiva cuando **todas las unidades del documento
  están procesadas**.
- `scripts/score_groundtruth_campaign.py` genera dos archivos adicionales:
  `data/evaluation/formal_metrics_by_document.csv` y
  `data/evaluation/formal_metrics_by_document.json`.
- El CSV por repetición deja **vacías las métricas de calidad global**
  cuando la repetición está incompleta, pero conserva cobertura y
  métricas de denominador global bajo nombres
  `*_full_corpus_coverage_adjusted`.
- Las unidades aún no ejecutadas
  (`pending_document_units`), la falta de predicciones en documentos
  intentados (`unavailable_in_started_documents`) y los errores
  explícitos (`explicit_unit_errors`) aparecen separados. Ninguno
  se convierte artificialmente en clase negativa.

Comprobar el cambio sin enviar nuevos datos a OpenRouter:

```powershell
git pull --ff-only origin experiment/groundtruth-evaluation
$env:PYTHONPATH = (Resolve-Path ".\\backend").Path
python -m pytest tests/unit/test_document_metrics.py tests/unit/test_repetition_metrics.py -q
python scripts/score_groundtruth_campaign.py --csv data/evaluation/ground_truth_547.csv
```

**No repetir ET01-R1**: la ejecución documental ya fue completada.
No alterar las etiquetas humanas ni el prompt en función de estos
primeros resultados si el objetivo es mantener una evaluación
confirmatoria válida; cualquier cambio deberá documentarse y
justificarse como experimento separado.

## Trabajos restantes antes de la evaluación del capítulo IV

- Verificar en VS Code el checkpoint de cláusulas y el evaluador por repetición.
- Auditar el corpus jurídico de ChromaDB y congelar configuración, modelos
  y revisión exacta del código antes de la campaña.
- Probar **una tarea documental completa** y validar su costo, informe,
  predicciones y trazas de Langfuse.
- Evaluar riesgos de facturación no reportada y controles de concurrencia.
- Completar las tareas formales con seguimiento, después realizar la
  comparación estadística y estudiar amenazas a la validez.

Los 10 ToS corresponden al alcance y a la Tabla 8 de la tesis.
