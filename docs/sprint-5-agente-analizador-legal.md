# Sprint 5 — Agente Analizador Legal

## Objetivo

Implementar el núcleo encargado de analizar cláusulas de términos
de servicio, recuperar normativa relacionada y clasificarlas según
su categoría y nivel de riesgo, generando una justificación
respaldada con fuentes jurídicas.

## Actividades desarrolladas

El Sprint 5 comprendió las actividades TIT-41 a TIT-48:

- Definición de categorías y niveles de riesgo.
- Configuración del acceso a modelos de lenguaje.
- Diseño de los prompts para el análisis jurídico.
- Implementación de la clasificación de cláusulas.
- Generación de justificaciones respaldadas mediante RAG.
- Implementación del Agente Analizador Legal.
- Implementación de su servidor MCP.
- Validación funcional mediante cláusulas controladas.

## Clasificación establecida

El agente utiliza las siguientes clasificaciones:

- `fair`: cláusula con riesgo bajo.
- `potentially_abusive`: cláusula con riesgo medio que requiere
  revisión humana.
- `abusive`: cláusula con riesgo alto y contradicción directa con
  evidencia jurídica aplicable.
- `requires_review`: resultado inconcluso debido a falta de
  contexto o evidencia suficiente.

También se establecieron categorías relacionadas con privacidad,
transferencia de datos, modificación y terminación unilateral,
limitación de responsabilidad, solución de controversias,
restricción de derechos del consumidor y propiedad intelectual.

## Acceso a modelos de lenguaje

Se implementó una puerta de acceso común para los modelos de
lenguaje. El sistema admite:

- Ollama como proveedor local para desarrollo.
- OpenRouter como proveedor remoto para validaciones posteriores.
- Modo automático con respaldo local cuando el proveedor remoto
  no se encuentre disponible.

Durante esta validación se utilizó Ollama con el modelo
`qwen3:4b`, temperatura `0.0` y contexto de 8192 tokens.

## Funcionamiento del agente

El Agente Analizador Legal recibe una cláusula previamente
procesada y ejecuta el siguiente flujo:

1. Construye la consulta jurídica.
2. Recupera segmentos normativos desde ChromaDB.
3. Envía la cláusula y las evidencias al modelo de lenguaje.
4. Valida la estructura de la respuesta.
5. Comprueba que los índices jurídicos existan.
6. Verifica que el fragmento señalado pertenezca a la cláusula.
7. Vincula la valoración con las fuentes seleccionadas.
8. Devuelve la categoría, clasificación, riesgo, justificación,
   recomendación y fundamentos jurídicos.

El agente fue expuesto mediante una herramienta MCP denominada
`analyze_legal_clause`.

## Controles implementados

Se incorporaron controles para impedir:

- Respuestas que no cumplan el esquema JSON.
- Índices jurídicos inexistentes o repetidos.
- Fragmentos que no pertenezcan a la cláusula.
- Clasificaciones sin fundamento jurídico.
- Resultados abusivos con evidencia insuficiente.
- Decisiones inconclusas que contengan una clasificación.
- Invención de fuentes o metadatos jurídicos.
- Uso de la distancia semántica como argumento jurídico.

El nivel de riesgo y la necesidad de revisión humana se calculan
de forma determinista a partir de la clasificación.

## Dataset de validación

Se definió el conjunto `tit48_legal_analysis_v1`, compuesto por
12 cláusulas controladas. Los casos incluyen modificaciones
unilaterales, terminación del servicio, limitación de
responsabilidad, arbitraje, transferencia y conservación de datos,
propiedad intelectual, cargos adicionales, cláusulas equilibradas
y cláusulas sin contexto suficiente.

Este conjunto se utilizó para validar el funcionamiento técnico
del agente. No constituye todavía un conjunto de referencia
jurídica definitivo, debido a que sus etiquetas y justificaciones
requieren revisión especializada.

## Línea base local

La primera ejecución completa produjo:

- Casos ejecutados: 12.
- Ejecuciones exitosas: 12.
- Errores técnicos: 0.
- Coincidencias automáticas completas: 8.
- Coincidencias de categoría: 11.
- Coincidencias de clasificación: 9.
- Resultados con fundamentos asociados: 12.
- Tiempo promedio: 48,274 segundos.
- Mediana: 46,366 segundos.
- Percentil 95: 67,295 segundos.

## Ajustes realizados

A partir de la línea base se realizaron los siguientes ajustes:

- Reglas más estrictas para determinar la aplicabilidad de las
  evidencias.
- Coherencia entre contradicción normativa y clasificación.
- Abstención cuando la cláusula o evidencia resulte insuficiente.
- Reducción de la extensión de justificaciones y recomendaciones.
- Eliminación de la distancia semántica de la entrada enviada al
  modelo.
- Ampliación del contexto local de 4096 a 8192 tokens.
- Registro opcional de respuestas inválidas para diagnóstico.
- Diferenciación entre coincidencia automática de campos y
  revisión jurídica manual.

## Resultado final local

La ejecución final con Ollama produjo:

- Casos ejecutados: 12.
- Ejecuciones exitosas: 12.
- Errores técnicos: 0.
- Coincidencias automáticas completas: 7.
- Coincidencias de categoría: 10.
- Coincidencias de clasificación: 8.
- Coincidencias de estado: 11.
- Cobertura del documento jurídico esperado: 11.
- Estructura de fundamentos válida: 12.
- Tiempo total: 680,454 segundos.
- Tiempo promedio: 56,705 segundos.
- Mediana: 56,404 segundos.
- Percentil 95: 65,550 segundos.

La ampliación del contexto evitó las respuestas estructuralmente
inconsistentes observadas durante las pruebas parciales, pero
incrementó el tiempo promedio y no produjo una mejora general en
las coincidencias automáticas.

## Incidencias identificadas

Durante la validación se identificaron los siguientes aspectos:

- ChromaDB requiere que Docker Desktop se encuentre activo.
- Una fuente existente no garantiza que sea jurídicamente
  aplicable a la cláusula.
- El modelo puede interpretar incorrectamente el sujeto obligado
  por una disposición.
- La coincidencia de categoría y documento no demuestra que toda
  la justificación sea correcta.
- Algunas cláusulas ambiguas fueron clasificadas cuando debieron
  remitirse a revisión.
- El procesamiento local secuencial presenta una latencia elevada
  para documentos con numerosas cláusulas.
- Los casos relacionados con propiedad intelectual y cargos
  adicionales requieren revisar sus referencias esperadas.

## Alcance de las métricas

Las métricas automáticas comparan categorías, clasificaciones,
riesgos, estados y presencia de documentos esperados. La presencia
de una fuente se considera trazabilidad estructural, pero no
demuestra por sí misma la pertinencia ni la corrección jurídica de
la justificación.

La validación jurídica definitiva requerirá un conjunto de
referencia revisado por una persona con conocimiento especializado
y una evaluación posterior con el proveedor remoto seleccionado.

## Conclusión

El Sprint 5 produjo un Agente Analizador Legal funcional, accesible
mediante MCP, capaz de recuperar normativa, clasificar cláusulas y
devolver valoraciones estructuradas con fuentes verificables.

La validación confirmó el funcionamiento técnico del flujo y
permitió identificar limitaciones de razonamiento y rendimiento.
Estas incidencias quedan registradas como insumos para la
integración, optimización y evaluación final del sistema.