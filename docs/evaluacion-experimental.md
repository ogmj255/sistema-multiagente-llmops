# Evaluación experimental — capítulo III, sección 3.7

Esta rama contiene la validación del ground truth, el cálculo de métricas y
el **plan experimental**. No ejecuta todavía modelos ni recuperaciones RAG
y no contiene resultados medidos.

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
son **candidatos de configuración**: verificar que cada ID existe y está
disponible en OpenRouter, registrar el modelo efectivamente devuelto y
congelar versiones antes de ejecutar. Los nombres académicos de la tesis
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
