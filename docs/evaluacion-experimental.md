# Evaluación experimental — capítulo III, sección 3.7

Esta rama contiene la validación del ground truth, el cálculo de métricas,
el **plan experimental** y un **ejecutor piloto limitado** con recuperación RAG,
selección de modelo y registro JSONL. No contiene resultados medidos todavía.

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
