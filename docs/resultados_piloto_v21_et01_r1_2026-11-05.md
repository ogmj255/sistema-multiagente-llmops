# Resultado exploratorio V2 vs V2.1 — ET01-R1 (Holded / DeepSeek)

**Fecha:** 2026-11-05.  
**Fuente primaria:** salida de consola aportada por el investigador del ejecutor `scripts.validate_prompt_v21 --execute` y `--compare`.  
**Estado:** piloto V2.1 completado; comparación exploratoria aprobada. **No equivale a validación confirmatoria de la mejora.**

## Identidad experimental

| Elemento | V2 | V2.1 |
| --- | --- | --- |
| Dataset fingerprint | `d1e589a83a2019cde901c61f7a1f850815642431701e19b5f349d90b57a13a84` | Igual |
| Tarea | ET01-R1 | ET01-R1 |
| Documento | ToS01 / Holded | ToS01 / Holded |
| Modelo | `deepseek/deepseek-v4-flash-0731` | Igual |
| Unidades | 21 (20 evaluables; 1 no aplicable) | Igual |
| Execution ID | `4545389a-b15b-456e-a6bb-d548d47a307b` | `b1228788-6fda-42f1-9aae-aa47db0d971a` |

Huella del preflight candidato V2.1: `1ef36bf3ea62aa78c7ae3d1e48bef89e7c673bd22916b8cdfa58db92c5a93ab8`, verificada sin invocar OpenRouter.

## Métricas reproducidas en la salida de comparación

| Indicador | V2 original | V2.1 candidato | Diferencia |
| --- | ---: | ---: | ---: |
| Exactitud binaria | 0.550000 | 0.600000 | +0.05 |
| F1 macro binario | 0.539642 | 0.583333 | +0.043691 |
| TN | 7 | 8 | +1 |
| FP | 9 | 8 | -1 |
| FN | 0 | 0 | 0 |
| TP | 4 | 4 | 0 |
| Precisión PA | 0.307692 | 0.333333 | +0.025641 |
| Recall PA | 1.0 | 1.0 | 0 |
| NPA F1 | 0.608696 | 0.666667 | +0.057971 |
| Aplicabilidad N/A correcta | 1/1 | 1/1 | 0 |
| Costo reportado USD | 0.01370225 | 0.01645207 | +0.00274982 (aprox. 20.1 %) |
| Duración reportada ms | 308839.150 | 355958.731 | +47119.581 (aprox. 15.3 %) |

## Modificaciones por unidad

| ID | Etiqueta humana | Predicción V2 | Predicción V2.1 | Interpretación |
| --- | --- | --- | --- | --- |
| ToS01-U006 | NPA | PA | NPA | Corrige FP |
| ToS01-U017 | NPA | NPA | PA | Nuevo FP |
| ToS01-U020 | NPA | PA | NPA | Corrige FP |

La mejora neta es **un acierto adicional en 20 cláusulas evaluables**. El criterio automatizado `candidate_passes_exploratory_gate` devolvió `true`, lo que permite proseguir con la **validación adicional**, pero no demuestra superioridad de V2.1 en otros documentos, repeticiones o modelos.

## Restricciones y decisión científica

1. El prompt V2.1 fue formulado *después* de inspeccionar los falsos positivos de Holded V2; por ello, Holded no es un conjunto de validación independiente.
2. Solo cuatro unidades de este documento son PA; la ausencia de FN es un dato limitado, no garantía de sensibilidad general.
3. La duración y el costo se incrementaron en este piloto. El costo reportado puede omitir intentos cuyo JSON fue rechazado; contrastar con Langfuse y facturación del proveedor.
4. Preservar intactos los archivos históricos V2 y el piloto V2.1, sus manifiestos, trazas y predicciones por unidad.
5. **No iniciar aún las 90 ejecuciones como prueba confirmatoria solo por este piloto.** Realizar validación adicional con cláusulas externas al conjunto usado para ajustar el prompt, usando criterios decididos por adelantado.
6. Cuando se adopte formalmente V2.1, congelar un nuevo manifiesto y una nueva ruta de resultados para las 90 tareas con tres modelos y tres repeticiones, desde cero. Jamás mezclar checkpoints ni resultados V2.
7. Registrar explícitamente en la tesis que hubo desarrollo exploratorio y selección de prompt antes de la evaluación final, para evitar presentar la comparación exploratoria como evidencia confirmatoria.

## Archivos locales que deben preservarse

- `data/evaluation/v2_binary_campaign_runs.jsonl` (V2, no alterar).
- `data/evaluation/v2_binary_preflight_manifest.json` (V2, no alterar).
- `data/evaluation/prompt_v2_1_candidate/preflight_manifest.json` (V2.1).
- `data/evaluation/prompt_v2_1_candidate/runs.jsonl` (V2.1).
- `data/evaluation/prompt_v2_1_candidate/comparison.json` (comparación).
- `data/evaluation/prompt_v2_1_candidate/unit_checkpoints.jsonl` (checkpoints V2.1).

**Próxima acción propuesta:** verificar integridad de las evidencias y el costo real, evaluar la robustez de V2.1 con datos independientes de ajuste, y solo entonces decidir si aprobar la campaña formal V2.1 de 90 tareas con almacenamiento exclusivo.
