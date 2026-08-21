# Validación de la eliminación de ruido — TIT-26

## Objetivo

Validar que el Agente Preprocesador elimine elementos sin información jurídica útil, conserve el contenido contractual y mantenga su orden original.

## Implementación

La limpieza utiliza metadatos estructurales obtenidos por el Web Scraper:

- Área HTML de origen.
- Etiqueta HTML.
- Encabezado y nivel jerárquico.
- Cantidad de enlaces.
- Identificación de bloques compuestos únicamente por enlaces.
- Orden original del bloque.

Se eliminan bloques pertenecientes a navegación, encabezados de interfaz, pies de página, elementos laterales e interactivos. También se eliminan enlaces aislados fuera del contenido principal y duplicados exactos consecutivos.

No se utilizan reglas por plataforma, palabras específicas ni límites de longitud.

## Validación automatizada

Se ejecutaron 32 pruebas unitarias.

Resultado:

- 32 pruebas aprobadas.
- Código validado mediante Ruff.
- Conservación del orden verificada.
- Contratos cortos permitidos.
- Contenido exclusivamente estructural rechazado.
- Duplicados anidados y consecutivos controlados.
- Fallback genérico comprobado.
- Tablas conservadas mediante filas completas.
- Elementos ocultos excluidos.

Se presentó una advertencia de deprecación generada por una dependencia de `TestClient`. Esta advertencia no afectó la ejecución de las pruebas.

## Validación con términos de servicio reales

| Plataforma | Estado | Cláusulas conservadas | Caracteres limpios |
| --- | --- | ---: | ---: |
| GitHub | Correcto | 165 | 45847 |
| Slack | Correcto | 26 | 13085 |
| Dropbox | Correcto | 96 | 25346 |
| Atlassian | Correcto | 137 | 46080 |
| HubSpot | Correcto | 217 | 65322 |

Resultado general: cinco de cinco contratos procesados correctamente.

En todas las plataformas se verificó:

- Inicio coherente del contenido contractual.
- Final coherente del contenido contractual.
- Eliminación de navegación y elementos de interfaz.
- Conservación del orden original.
- Ausencia de falsos positivos conocidos.
- Tiempo de procesamiento de pocos segundos.

## Decisiones técnicas

- El procesamiento es determinista y no utiliza un modelo de lenguaje.
- Los elementos HTML semánticos tienen prioridad.
- Los contenedores genéricos `div` y `section` se utilizan únicamente cuando no existe contenido semántico utilizable.
- La limpieza avanzada se realiza en el Agente Preprocesador.
- No se limita la cantidad de secciones, caracteres o cláusulas.

## Resultado

La implementación cumple los criterios de aceptación de TIT-26: elimina ruido estructural, conserva el texto contractual y su orden lógico, y fue validada con cinco términos de servicio reales.
