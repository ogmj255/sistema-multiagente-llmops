# Auditoría preliminar de la validación apareada ET04-R1 (ToS02/OpenAI)

**Fuente de cifras:** JSON que el investigador copió de
scripts.validate_v21_holdout --compare tras completar ambas
condiciones del holdout. **Fecha de ejecución informada:** 6/11/2026.

**Estado del criterio pre-registrado:** passes_preregistered_gate=false.

## Identificadores e integridad

- Protocolo de validación: PREREGISTERED_SINGLE_DOCUMENT_HOLDOUT.
- Huella holdout: 8e14067e325b9d240ddab14e6e6dce6256ad718cf0e3503a67d927ddac442ba9.
- Dataset: d1e589a83a2019cde901c61f7a1f850815642431701e19b5f349d90b57a13a84.
- Referencia V2: 041de92c-6b74-4a4a-ab59-d1d688decaca.
- Candidata V2.1: 33e62659-31bd-447a-a4a2-11a85d8d2228.
- Total unidades: 40; evaluables NPA/PA: 37; N/A humanas: 3.

## Resultado de la comparación

| Indicador | V2 | V2.1 | Delta |
| --- | ---: | ---: | ---: |
| Exactitud binaria sobre evaluables | 0,594595 | 0,567568 | -0,027027 |
| F1 macro | 0,571195 | 0,559562 | -0,011633 |
| VP PA | 6 | 7 | +1 |
| VN NPA | 16 | 14 | -2 |
| FP | 13 | 15 | +2 |
| FN | 1 | 0 | -1 |
| Recall PA | 0,857143 | 1,0 | +0,142857 |
| No aplicables correctamente detectadas | 0/3 | 0/3 | 0 |
| Costo reportado USD | 0,03195609 | 0,03940101 | +0,00744492 |
| Duración ms | 1.611.004,279 | 897.475,389 | -713.528,890 |

La versión V2.1 aumentó la sensibilidad a PA y corrigió un falso
negativo (ToS02-U012), pero empeoró el F1 macro y la exactitud,
incrementando el número de falsos positivos. De 9 decisiones
modificadas, 5 pasaron de acierto V2 a error V2.1, y 4 de error V2
a acierto V2.1. La prueba exacta apareada de McNemar arroja p=1,0,
por lo que no se sustenta una diferencia concluyente con este tamaño
de muestra.

## Dos anomalías que ameritan auditoría de solo lectura

### 1. Matriz binaria de 36 observaciones para 37 unidades evaluables

La suma TP+TN+FP+FN es 36 en ambas versiones (6+16+13+1;
7+14+15+0), aunque hay 37 unidades evaluables. Según el código
binary_scoring.py, la matriz tiene además una columna not_applicable.
Por tanto, se espera que **una unidad evaluable se haya predicho como
not_applicable** en ambas versiones (no necesariamente el mismo ID).
Esa predicción se contabiliza como error en exactitud y F1, pero
no dentro de las cuatro celdas NPA/PA que muestra el resumen.

Además, las tres unidades humanas not_applicable fueron
incorrectamente clasificados en ambas versiones (0/3 correctas).
Auditar IDs y salidas concretas: problema de aplicabilidad, no solo
de desempeño binario.

### 2. Contextos RAG no idénticos

Se recuperaron 40 contextos en cada ejecución, pero se detectaron
cuatro discrepancias de SHA-256 de las respuestas. **No está probado
todavía que difieran en sus fuentes o contenido jurídico**: podrían
ser diferencias de distancias numéricas, orden o contenido recuperado.
El campo mismatched_query_hashes contiene hashes canónicos de la
configuración de consulta, no IDs de cláusulas. Deben vincularse
con IDs técnicos y compararse segmentos jurídicos y distancias en
modo lectura antes de atribuir toda diferencia al prompt.

Si las fuentes/evidencia difieren materialmente, el tratamiento
experimental no aísla perfectamente la variable prompt. No alterar
RAG ni ejecutar otra inferencia para disimular o reemplazar el incidente.

## Regla metodológica y decisión

El filtro pre-registrado exigía simultáneamente delta F1 macro >=0,02,
FN no creciente, aplicabilidad no peor y equivalencia exacta del
contexto RAG. Se incumplen al menos dos: F1 (-0,011633) y equivalencia
RAG. Por tanto, **se rechaza la hipótesis operativa de que V2.1
superó este holdout**. No concluir que V2 sea superior en la
población de cláusulas, ni que la mejora Holded fuera inválida.

No iniciar campaña formal V2.1 de 90 tareas; no reajustar los prompts
tras observar el holdout y denominar la siguiente prueba "independiente".
Conservar todo el historial V2, V2.1, los dos pilotos y los manifiestos.

## Auditoría local propuesta, sin facturación

Con la rama experiment/v21-holdout-validation, ejecutar:

~~~powershell
$env:PYTHONPATH = (Resolve-Path ".\backend").Path
python -m pytest tests/unit/test_v21_holdout_audit_readonly.py -q
docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.audit_v21_holdout_readonly
~~~

Este script no cambia resultados ni llama OpenRouter. Sí puede consultar
Chroma y Ollama en modo lectura al verificar los manifiestos.
Imprime la matriz de tres estados, IDs con errores de aplicabilidad
y, por cada discrepancia RAG, el ID técnico, identidad de fuentes y
diferencias de distancias sin revelar contenido contractual.

## Auditoría de solo lectura completada

El investigador ejecutó las pruebas de la auditoría original y obtuvo
**4 passed in 10.18s**. La ejecución de auditoría posterior mantuvo
las huellas congeladas y concretó cuatro discordancias de aplicabilidad,
idénticas en V2 y V2.1:

| Unidad | Referencia | Predicción V2 | Predicción V2.1 |
| --- | --- | --- | --- |
| ToS02-U001 | not_applicable | NPA | NPA |
| ToS02-U002 | not_applicable | NPA | NPA |
| ToS02-U011 | NPA | not_applicable | not_applicable |
| ToS02-U023 | not_applicable | NPA | NPA |

La exactitud de aplicabilidad binaria es 36/40 = 90 % para ambas
versiones, pero recall no aplicable = 0/3 = 0 %. La unidad U011
explica que las cuatro celdas de riesgo sumen 36 en vez de 37,
pues una NPA se predijo como no aplicable.

Las cuatro diferencias RAG fueron U037, U038, U039 y U040.
En U037/U039/U040 coinciden los cinco segmentos, el orden y
su contenido; difieren únicamente las distancias registradas.
En U038 el orden o la identidad del material recuperado difiere:
la primera auditoría no distingue todavía orden cambiado de
segmentos sustituidos. La auditoría de lectura se amplió para
comparar los mismos segmentos ignorando el orden.

Ninguno de los cuatro IDs U037–U040 aparece entre los nueve IDs
cuya predicción cambió entre V2 y V2.1 (U004, U006, U010, U012,
U018, U020, U024, U032, U036). Por ello las divergencias RAG
no explican directamente los cambios de etiqueta en este ensayo,
aunque el criterio de equivalencia exacta RAG sigue sin cumplirse.

### Inspección siguiente, sin facturación

Se añadió un lector del texto original completo y las
justificaciones V2 y V2.1 únicamente para cuatro discordancias
de aplicabilidad. No modifica etiquetas ni resultados:

    python -m pytest tests/unit/test_v21_inspect_disagreements_readonly.py -q
    docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.inspect_v21_disagreements_readonly

Para distinguir reordenamiento de sustitución de segmentos en U038:

    python -m pytest tests/unit/test_v21_holdout_audit_readonly.py -q
    docker compose --profile experiment run --rm --no-deps evaluation-worker python -m scripts.audit_v21_holdout_readonly

El informe ampliado añade same_unordered_legal_chunks y
same_unordered_source_content_excluding_distance para todas las
discrepancias, sin modificar los snapshots originales.

**Decisión científica:** la candidata V2.1 no superó el holdout.
Los cuatro errores de aplicabilidad merecen inspección textual
humana antes de proponer cambios. No iniciar la campaña de 90
tareas V2.1 ni denominar independientes las pruebas ya observadas.
