# Validación exploratoria de prompt V2.1

## Estado y principio de preservación

La V2 original tiene ET01-R1 Holded/DeepSeek completada:
21 cláusulas, 20 evaluables, exactitud 0,55, F1 macro 0,5396,
costo de campaña reportado USD 0,01370 y un error de esquema recuperado.

**No borrar, modificar ni reutilizar resultados o checkpoints V2.**
El proyecto candidato usa la rama experiment/prompt-v2-1-validation.
Se modifica exclusivamente el prompt; no cambian el esquema JSON,
los modelos, RAG, orquestación o ground truth de 547 unidades.

## Seis ajustes propuestos

1. Consequence: efecto o sanción expresamente establecidos; si no, null.
2. Habitualidad: la frecuencia no determina NPA ni PA.
3. Truncamiento: no reconstruir cláusulas; PA requiere indicio textual.
4. Disposiciones múltiples: única etiqueta y valoración contextual de
   excepciones y protecciones explícitas.
5. Evidence sufficiency: respaldo jurídico recuperado, no intensidad del riesgo.
6. Descripciones en español, códigos de salida estables, ningún campo extra.

El esquema continúa rechazando strict y otros campos adicionales.
Estas mejoras no garantizan por sí mismas más calidad ni menos errores
de salida; necesitan comprobación en una ejecución real.

## Arquitectura y aislamiento

El nuevo ejecutor scripts/validate_prompt_v21.py conserva el
LangGraph y los MCP reales: no hace inferencias directas al proveedor.
Acepta exactamente una tarea piloto, ET01-R1 (Holded, T1 DeepSeek, R1).
Contrasta el preflight histórico de V2 sin sobrescribirlo y comprueba
los mismos datos, la colección RAG, embeddings, modelos y temperatura.

La única carpeta nueva de salida es:
data/evaluation/prompt_v2_1_candidate/

Archivos propios: preflight_manifest.json, runs.jsonl,
unit_checkpoints.jsonl, legal_context_snapshots.jsonl, comparison.json.
El ejecutor rechaza un nuevo intento si ya existe un registro candidato.

**No usar scripts/preflight_binary_worker.py sobre V2.1**, pues
correctamente rechazaría una configuración distinta a la V2 congelada.

## Etapa A: verificar el código, sin gastar créditos

Ejecutar en PowerShell desde la raíz del repositorio:

~~~powershell
git status --short
git fetch origin
git switch --track origin/experiment/prompt-v2-1-validation

$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_v21_prompt_semantics.py tests/unit/test_prompt_v21_validation_runner.py -q
python -m pytest tests/unit -q
docker compose --profile experiment config --quiet
~~~

Si la rama local existe, usar git switch experiment/prompt-v2-1-validation
en lugar de git switch --track.

**Antes de reconstruir imágenes**:
verificar en Streamlit que no exista ningún trabajo V2 ejecutándose
o en cola. Dejar EXPERIMENT_EXECUTION_ENABLED=false en el archivo .env
de la raíz; luego ejecutar:

~~~powershell
docker compose up -d --no-deps --force-recreate backend
docker compose --profile experiment stop evaluation-worker
~~~

No detener el worker durante una solicitud de pago. No recrear el backend
original después de reconstruir la imagen candidata: comparten la
etiqueta de imagen clausulas-backend:0.1, aunque el contenedor histórico
ya ejecutándose conserva su imagen anterior.

## Etapa B: preflight V2.1 sin inferencias

~~~powershell
docker compose --profile experiment build evaluation-worker
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_prompt_v21 --freeze
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_prompt_v21 --verify
~~~

Deben aparecer las confirmaciones PREFLIGHT V2.1 CONGELADO y
PREFLIGHT V2.1 APROBADO, con una huella nueva distinta de V2.
La referencia original V2 queda sin cambios.

## Etapa C: piloto candidato real, con autorización y posible gasto

Solamente con pruebas aprobadas, worker histórico detenido,
facturación V2 deshabilitada y saldo OpenRouter comprobado:

~~~powershell
docker compose --profile experiment run --rm --no-deps -e V21_CANDIDATE_EXECUTION_ENABLED=true evaluation-worker python -m scripts.validate_prompt_v21 --execute --confirm-paid-run --max-reported-cost-usd 0.10
~~~

Este comando procesa solo 21 cláusulas Holded con DeepSeek, usando
LangGraph + MCP + RAG + OpenRouter + Langfuse reales.

**USD 0,10 es un límite BLANDO entre documentos, no un máximo garantizado
para el documento actual.** Los intentos inválidos también podrían
facturarse y no verse en el costo reportado del resultado.

No lanzar de nuevo el mismo comando si hubo un resultado incompleto:
primero auditar el registro, los checkpoints y el estado de facturación.

## Etapa D: comparación sin gasto

~~~powershell
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.validate_prompt_v21 --compare
~~~

Se genera comparison.json con exactitud, F1 macro NPA/PA,
falsos positivos, falsos negativos, duración, costos reportados,
ejecución de referencia y los IDs de las predicciones cambiadas.

**Criterio exploratorio registrado antes de ejecutar V2.1**:
F1 macro superior a V2, menos falsos positivos, ningún falso negativo
adicional, ninguna pérdida de aciertos de aplicabilidad (1/1 en la
referencia V2) y las 21 unidades procesadas. Revisar asimismo incidencias de
formato JSON, repetición de llamadas, trazas Langfuse, costos totales
y diagnóstico de aplicabilidad. Un solo documento no demuestra
superioridad; Holded ya se examinó al diseñar estas mejoras.

## Etapa E: decisión sobre iniciar desde cero

Si V2.1 no mejora, mantener la campaña V2 y documentar el piloto.
Si es prometedora, validar con datos no usados para ajustar las reglas;
si se confirma la ventaja y el tutor acepta el cambio metodológico,
crear una nueva campaña V2.1 de 90 tareas con directorios, claves de
configuración y manifiesto propios, sin reutilizar inferencias V2.

La ejecución masiva no se activa automáticamente. No fusionar esta
rama ni reemplazar la aplicación V2 hasta completar la revisión.
