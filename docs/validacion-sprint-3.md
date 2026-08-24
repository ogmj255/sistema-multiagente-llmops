# Validación del Sprint 3 — Agente Preprocesador

## Fecha

24 de agosto de 2026.

## Objetivo del sprint

Implementar un Agente Preprocesador que reciba contratos extraídos por el Agente Web Scraper, elimine ruido estructural, normalice el texto y genere cláusulas ordenadas con una salida validada y trazable.

## Alcance

El preprocesador recibe un contrato estructurado mediante `ExtractedContract` y produce un `PreprocessedContract`.

El resultado incluye:

- Metadatos del contrato.
- Texto limpio.
- Cláusulas estructuradas y ordenadas.
- Orden original de cada cláusula.
- Encabezados y niveles jerárquicos.
- Bloques eliminados y motivo de eliminación.
- Respuesta controlada ante errores.

La construcción del índice Vectorless RAG y la navegación jerárquica corresponden al Sprint 4.

## Componentes implementados

| Componente | Responsabilidad |
|---|---|
| Reglas de preprocesamiento | Definir la normalización, limpieza y segmentación |
| Servicio de texto | Normalizar y limpiar las secciones extraídas |
| Segmentador | Convertir las secciones en cláusulas ordenadas |
| Esquemas Pydantic | Validar la entrada y la salida |
| Agente Preprocesador | Coordinar el flujo completo |
| Servidor MCP | Exponer el preprocesamiento como herramienta |
| Pruebas automatizadas | Verificar resultados y errores principales |
| Script de validación | Ejecutar contratos SaaS de complejidad variable |

## Flujo de preprocesamiento

1. El Agente Web Scraper obtiene el contrato.
2. El Agente Preprocesador recibe el objeto `ExtractedContract`.
3. Se normalizan la codificación, espacios y caracteres.
4. Se eliminan bloques estructurales de navegación, encabezado y pie de página.
5. Se conservan las secciones contractuales y su orden original.
6. Se generan cláusulas estructuradas.
7. Se construye el texto limpio.
8. Se devuelve una respuesta de éxito o un error controlado.

## Validación con ToS de complejidad variable

Se reutilizó el conjunto de plataformas SaaS definido durante el Sprint 2.

| Complejidad | Plataforma | Método | Secciones | Cláusulas | Eliminados | Caracteres limpios | Tiempo |
|---|---|---|---:|---:|---:|---:|---:|
| Baja | Slack | Playwright | 82 | 33 | 49 | 14206 | 21.35 s |
| Media | Dropbox | Beautiful Soup | 175 | 96 | 79 | 25346 | 18.05 s |
| Media | GitHub | Playwright | 210 | 166 | 44 | 45931 | 13.56 s |
| Alta | Atlassian | Playwright | 218 | 152 | 66 | 48725 | 13.25 s |
| Alta | HubSpot | Beautiful Soup | 302 | 222 | 80 | 65447 | 8.08 s |

Resultado general: cinco de cinco contratos fueron extraídos y preprocesados correctamente.

Las pruebas incluyeron ambos métodos de extracción y contratos con diferentes cantidades de contenido, secciones y ruido estructural.

## Ejecución reproducible

La validación puede repetirse mediante:

```powershell
$env:PYTHONPATH = "backend"
python "scripts\test_preprocessor_agent.py"