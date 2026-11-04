# Evaluación experimental — fase 1 (base verificable)

Esta rama añade la **validación del corpus y el evaluador de predicciones**.
Aún no ejecuta tres modelos, RAG ni el pipeline de LangGraph. No hay
resultados experimentales reales en este cambio.

## Fuente y confidencialidad

Exportar la hoja única de \`ANEXO-GroundTruth.xlsx\` a CSV UTF-8 sin editar
ID, texto, aplicabilidad ni etiqueta. Guardarla localmente como
\`data/evaluation/ground_truth_547.csv\` (excluida de Git por \`.gitignore\`).
No subir el archivo etiquetado a prompts, ChromaDB ni repositorios públicos.

La referencia validada aún requiere resolver la discrepancia documental
\`ToS05-U002\` y dejar constancia del cierre de auditoría. No usar las
etiquetas para ajustar modelos sobre las mismas unidades destinadas a
evaluación final.

Desde la raíz del repositorio:

\`\`\`bash
cd backend
python ../scripts/evaluate_groundtruth.py --csv ../data/evaluation/ground_truth_547.csv
\`\`\`

Se obtiene un manifiesto con las 547 unidades, distribución de clases,
plataformas, SHA-256 del archivo y huella reproducible de filas y etiquetas.

## Formato previsto para predicciones de cada modelo

Guardar JSONL fuera del control de versiones, una línea por intento:

\`\`\`json
{"id":"ToS01-U001","model":"modelo-real","dataset_fingerprint":"HUELLA_DEL_MANIFIESTO","status":"success","prediction":"potencialmente abusiva"}
\`\`\`

Las predicciones deben generarse **sin acceso a \`Etiqueta final\`**.
El identificador y la huella permiten detectar mezcla de versiones.
Si faltan predicciones, se contabilizan como fallos, no se eliminan
silenciosamente del denominador. Para puntuarlas:

\`\`\`bash
cd backend
python ../scripts/evaluate_groundtruth.py \
  --csv ../data/evaluation/ground_truth_547.csv \
  --predictions ../data/evaluation/predicciones.jsonl \
  --model modelo-real \
  --output ../data/evaluation/metricas-modelo-real.json
\`\`\`

El informe incluye matriz de confusión, precisión, recall, F1,
exactitud y cobertura de predicción, separando cuatro clases (todo
el corpus) y tres clases (solo fragmentos evaluables). No se debe
interpretar una métrica baja como fracaso técnico automático.

## Pendiente antes de la ejecución oficial

- Seleccionar y fijar las versiones reales de los tres modelos.
- Implementar el ejecutor usando el analizador existente y Langfuse,
  separando las etiquetas humanas de cualquier solicitud al modelo.
- Verificar que el corpus de 10 ToS cumple el requisito académico
  previamente planteado de al menos 15 ToS, o ampliar la evaluación.
- Congelar configuración, evidencia RAG y conjunto final antes de medir.

Pruebas de esta fase:
\`PYTHONPATH=backend pytest tests/unit/test_groundtruth_evaluation.py -q\`.
