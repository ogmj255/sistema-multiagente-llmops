# Validación TIT-28 — Algoritmo de segmentación de cláusulas

## Objetivo

Implementar y verificar el algoritmo que transforma las secciones contractuales limpias en cláusulas estructuradas, conservando el significado y el orden del documento original.

## Entrada y salida

El algoritmo recibe una lista de objetos `ContractSection` producida por la etapa de limpieza.

Como resultado, genera una lista de objetos `ProcessedClause` con:

- Orden consecutivo de la cláusula.
- Orden original dentro del documento.
- Encabezado asociado.
- Nivel del encabezado.
- Contenido contractual completo.

## Reglas del algoritmo

1. Cada bloque contractual limpio se convierte en una cláusula.
2. Los párrafos, elementos de listas y filas de tablas se conservan completos.
3. Las cláusulas mantienen el orden original del contrato.
4. La numeración de salida comienza en uno y es consecutiva.
5. Se conserva el orden original como metadato trazable.
6. Cada cláusula mantiene el encabezado estructural detectado.
7. El título del documento se utiliza como respaldo cuando no existe un encabezado.
8. No se divide una oración por la mitad.
9. No se utilizan límites de palabras, caracteres o tokens.
10. No se aplican reglas específicas para una plataforma SaaS.

## Control de errores

El servicio controla los siguientes casos:

- Entrada sin secciones contractuales.
- Secciones con órdenes duplicados.
- Secciones cuyo orden original no es ascendente.

Los errores son capturados por el Agente Preprocesador y se convierten en una respuesta con estado `error`, sin provocar la interrupción no controlada del sistema.

## Pruebas representativas

Se verificaron los siguientes escenarios:

- Segmentación de párrafos contractuales.
- Conservación de elementos numerados de listas.
- Conservación de filas completas de tablas.
- Asociación de encabezados.
- Uso del título como encabezado de respaldo.
- Conservación del orden lógico.
- Procesamiento de 200 secciones sin límite artificial de longitud.
- Rechazo de una entrada vacía.
- Rechazo de órdenes inconsistentes.
- Respuesta controlada del agente ante un error del segmentador.

Las pruebas reales con GitHub, Slack, Dropbox, Atlassian y HubSpot ya se encuentran documentadas en `docs/validacion-tit-26.md` y utilizan este mismo pipeline estructural.

## Validación técnica

Se ejecutaron las siguientes verificaciones:

- Ruff sobre el back-end, las pruebas y los scripts.
- Compilación del código Python mediante `compileall`.
- Suite completa de pruebas unitarias.

Resultado:

- 40 pruebas aprobadas.
- Sin errores de estilo.
- Sin errores de compilación.
- Sin errores bloqueantes.

La advertencia de deprecación de Starlette pertenece a una dependencia externa del cliente de pruebas y no afecta al algoritmo implementado.

## Cumplimiento

La funcionalidad recibe las entradas previstas, genera cláusulas estructuradas, conserva el orden y los encabezados, controla los errores principales y cuenta con pruebas y evidencia documentada.
