# Evaluación experimental — capítulo III, sección 3.7

Esta rama contiene validación del ground truth, métricas, plan experimental,
un piloto aislado y un **piloto multiagente vía LangGraph + MCP**. Las pruebas
unitarias y la ejecución real de este último están pendientes de verificación.

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

**Mistral ET02-R1** falló previamente por HTTP 429 y está registrado en
`orchestrated_runs.jsonl`. Cuando la prueba pase, para un intento
**explícito** después de verificar límites y disponibilidad:

```powershell
python scripts/run_orchestrated_experiment.py --csv data/evaluation/ground_truth_547.csv --task-id ET02-R1 --unit-id ToS01-U001 --execute --retry-errors
```

No repetir DeepSeek ni Kimi. Mantener los intentos fallidos como evidencia
operativa y documentar que una repetición posterior recuperó un fallo técnico.
Antes de ampliar a 90 ejecuciones, definir una estrategia de presupuesto y
concurrencia. Esta política no garantiza que el proveedor admita la solicitud.

## Etapas pendientes

1. Verificar los tres IDs exactos y sus restricciones de salida estructurada.
2. Crear el ejecutor integrado con el analizador jurídico existente y
   las trazas Langfuse, conservando las **tres repeticiones por unidad**
   identificadas por tarea, modelo y run independiente.
3. Prevenir reutilización de reportes previos y filtración de etiquetas
   humanas. Congelar o reproducir contexto RAG entre tratamientos.
4. Realizar piloto técnico sin optimizar prompts sobre el conjunto final,
   y después ejecutar las 90 tareas.
5. Agregar resultados operativos y comparaciones estadísticas; el
   evaluador actual para predicciones JSONL sirve como base, pero
   **todavía no calcula métricas agrupadas por repetición**.

Los 10 ToS de esta investigación son los que constan en el alcance,
la muestra y la Tabla 8 de la tesis. No existe en esta versión
un requisito de 15 documentos.
