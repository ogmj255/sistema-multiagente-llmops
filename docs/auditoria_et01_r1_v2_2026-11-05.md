# Auditoría parcial ET01-R1 — Holded / DeepSeek (NPA/PA V2)
**Fecha de evidencias:** 2026-11-05
**Estado:** revisión documental de las capturas de Streamlit y la exportación de trazas Langfuse aportadas por el investigador. No se alteraron resultados ni se accedió al directorio local de ejecución.

## Identificación
- Tarea: `ET01-R1`; documento `ToS01` (Holded); tratamiento `T1`; repetición `R1`.
- Modelo: `deepseek/deepseek-v4-flash-0731`.
- Ejecución: `4545389a-b15b-456e-a6bb-d548d47a307b`.
- Huella preflight V2 previamente registrada: `463397e33acf0d50e46e50fb6d345925e047bdf5968c49c4a6c749135cfc7eb4`.
- Campaña en la captura: 1/90 completadas; 89 pendientes; cero tareas documentales fallidas.

## Calidad — clasificación principal (20 evaluables)
| Ground truth | Predicción NPA | Predicción PA |
| --- | ---: | ---: |
| NPA | 7 | 9 |
| PA | 0 | 4 |

- Exactitud: 11/20 = **0,55**; F1 macro: **0,5396**.
- Clase NPA: precisión 1, recall 0,4375, F1 0,6087.
- Clase PA: precisión 0,3077, recall 1, F1 0,4706.
- La no aplicable adicional fue clasificada `not_applicable` (1/1): el diagnóstico de tres estados presenta 1 acierto N/A, 7 NPA correctas, 9 NPA→PA y 4 PA correctas.
- No extrapolar las métricas del documento a las 547 unidades ni a los otros modelos o repeticiones.

## Trazabilidad — incidencia técnica recuperada
La vista de Langfuse del mismo identificador de ejecución informa aproximadamente **5 min 03 s**, **135 mil tokens** y **USD 0,014** mostrados en formato redondeado. La tabla de filtros registra 22 generaciones `openrouter-generation`, 21 recuperaciones jurídicas MCP y 1 observación con estado ERROR del agente legal.

El error visible corresponde a validación Pydantic de `ClauseAnalysisDecision`: se recibió un campo adicional `strict: true` que el modelo de respuesta no permite (`extra_forbidden`). Este hallazgo **no demuestra un fallo del corpus ni del RAG**. La causa precisa de la inclusión del campo en el JSON de salida requiere inspección adicional de la respuesta original, si está registrada, sin activar registros con información sensible.

Código examinado:
- `backend/app/services/analysis.py`: `ClauseAnalysisDecision.model_validate_json(model_response.content)`; las respuestas inválidas provocan `ClauseClassificationError`.
- `backend/app/agents/legal_analyzer_agent.py`: si ocurre `ClauseClassificationError`, el agente retorna estado de error con `llm_metrics=None`.
- `backend/app/agents/orchestrator_agent.py`: `ejecutar_con_reintentos` permite `MAX_INTENTOS=2` para `RuntimeError`, por lo que una nueva respuesta válida puede recuperar la unidad.
- `backend/app/evaluation/campaign.py`: `sum_reported_cost` suma únicamente costos incluidos en los registros `llm_metrics`.

**Implicación:** las 22 generaciones observadas son consistentes con 21 respuestas documentales exitosas y **un intento de clasificación rechazado y recuperado**, sin que esto implique una tarea documental fallida. Se debe verificar la secuencia exacta antes de afirmar una recuperación específica por ID técnico.

## Costo y alcance de la medición
- Costo reportado por el módulo de campaña: **USD 0,01370**.
- Costo mostrado por Langfuse en la cabecera: **aprox. USD 0,014** (redondeado).
- La generación fallida visible presenta un costo de **USD 0,000197** en la traza.
- Debido a que el intento fallido no genera métricas válidas en el objeto de respuesta del analizador, **puede estar excluido** de `llm_metrics` y, por consiguiente, del costo consolidado de la campaña. `0,01370 + 0,000197 = 0,013897`, coherente con la visualización aproximada de Langfuse, pero no sustituye una conciliación del detalle de facturación de OpenRouter.

No presentar USD 0,01370 como costo exhaustivo de todos los intentos facturables sin conciliación con el proveedor.

## Decisiones de preservación
1. **No borrar** `ET01-R1`, sus checkpoints ni sus JSONL. Mantener sus métricas y la traza intactas.
2. **No cambiar** los archivos incluidos en la huella del preflight antes de terminar la campaña V2; corregir parsers o prompts bajo una versión de protocolo separada, o documentar y rehacer todo el preflight/campaña bajo reglas consistentes.
3. Registrar por separado las métricas de **calidad jurídica** (21 resultados completos; 20 evaluables) y **confiabilidad operativa** (22 generaciones observadas y una incidencia de esquema recuperada).
4. Verificar la conciliación de costo reportado en JSONL, costo acumulado Langfuse y facturación OpenRouter.
5. Conservar el JSON de predicciones y la traza vinculada a su ejecución y versión de modelo.

**Estado de auditoría:** calidad y aplicabilidad verificadas por capturas; pendiente conciliación detallada de facturación/retentos, revisión del JSON documental completo y vinculación por ID técnico del intento fallido. No corresponde declarar la auditoría integral cerrada todavía.
