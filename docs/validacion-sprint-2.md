# Validación del Sprint 2 — Agente Web Scraper

## Fecha

11 de agosto de 2026.

## Objetivo del sprint

Desarrollar un agente Web Scraper que permita extraer automáticamente términos de servicio publicados en páginas web de plataformas SaaS. El agente utiliza Beautiful Soup para contenido HTML estático y Playwright para páginas que requieren la ejecución de JavaScript.

## Alcance

El agente procesa una URL pública proporcionada por el usuario y devuelve el texto del contrato junto con sus metadatos. La limpieza avanzada, el preprocesamiento y el análisis de cláusulas se realizarán en los siguientes sprints.

## Componentes implementados

| Componente | Responsabilidad |
|---|---|
| Esquemas Pydantic | Validar la solicitud, las secciones y la respuesta |
| Servicio Web Scraper | Descargar y organizar el contenido HTML |
| Beautiful Soup | Procesar páginas con contenido estático |
| Playwright | Procesar páginas con contenido dinámico |
| Agente Web Scraper | Coordinar los métodos de extracción |
| MCP | Exponer el agente como una herramienta |
| Docker | Proporcionar un entorno reproducible |

## Flujo de extracción

1. El usuario proporciona una URL pública.
2. El agente intenta la extracción mediante Beautiful Soup.
3. Si la extracción estática falla o resulta insuficiente, el agente utiliza Playwright.
4. El contenido se organiza en secciones.
5. Se devuelven el texto y los metadatos del contrato.
6. Si ambos métodos fallan, se devuelve un mensaje de error.

## Validación con plataformas SaaS reales

| Plataforma | Estado | Método | Secciones | Caracteres |
|---|---|---|---:|---:|
| GitHub | Correcto | Beautiful Soup | 237 | 44199 |
| Slack | Correcto | Beautiful Soup | 265 | 17999 |
| Dropbox | Correcto | Beautiful Soup | 220 | 27496 |
| Atlassian | Correcto | Beautiful Soup | 206 | 47887 |
| HubSpot | Correcto | Beautiful Soup | 447 | 69264 |

Resultado general: cinco de cinco extracciones completadas correctamente.

## Validación del contenido dinámico

La extracción mediante Playwright se comprobó utilizando los términos de servicio de Slack.

| Campo | Resultado |
|---|---|
| Plataforma | Slack |
| Estado | Correcto |
| Método | Playwright |
| Secciones | 270 |
| Caracteres | 18694 |
| Primer encabezado | Sin encabezado inicial |
| Primer contenido  | Channels Organize teams and work   |

## Pruebas complementarias

Durante el desarrollo también se realizaron pruebas con Zoom y Netflix. Ambas páginas pudieron procesarse correctamente al extraer el contenido visible desde el cuerpo completo del documento HTML.

| Plataforma | Estado | Método |
|---|---|---|
| Zoom | Correcto | Beautiful Soup |
| Netflix | Correcto | Beautiful Soup |

Las pruebas complementarias demostraron que la estructura HTML varía entre plataformas. Por este motivo, el scraper conserva el texto visible del cuerpo completo y delega la limpieza al agente preprocesador del Sprint 3.

## Pruebas automatizadas

Se ejecutaron catorce pruebas unitarias relacionadas con:

- Validación de los esquemas del contrato.
- Endpoints principales de FastAPI.
- Extracción de HTML estático.
- Verificación de contenido suficiente.
- Eliminación de duplicados.
- Extracción del texto visible desde el cuerpo completo del documento.
- Cambio automático hacia Playwright.
- Manejo controlado cuando ambos métodos de extracción fallan.
- Rechazo de extracciones con contenido insuficiente.
- Exposición de la herramienta mediante MCP.

Resultado: catorce pruebas aprobadas.

Se presentó una advertencia de deprecación generada por una dependencia de `TestClient`. Esta advertencia no afectó la ejecución ni el resultado de las pruebas.

## Validación mediante MCP

El servidor MCP fue comprobado mediante MCP Inspector y desde el contenedor Docker. La herramienta disponible es:

`extract_saas_terms`

Esta herramienta recibe una URL y el nombre opcional de la plataforma, ejecuta el agente Web Scraper y devuelve el contrato estructurado.

## Validación en Docker

La imagen `clausulas-backend:0.1` fue construida con Python, las dependencias del backend y Chromium para Playwright.

Los servicios ejecutados fueron:

- FastAPI.
- PostgreSQL.
- Traefik.

El endpoint `/health` respondió correctamente y la herramienta MCP fue localizada dentro del contenedor.

## Cumplimiento de las actividades de Jira

| Actividad | Resultado |
|---|---|
| TIT-17 — Definir requisitos y fuentes | Completado |
| TIT-18 — Diseñar la estructura de datos | Completado |
| TIT-19 — Implementar Beautiful Soup | Completado |
| TIT-20 — Implementar Playwright | Completado |
| TIT-21 — Capturar texto y metadatos | Completado |
| TIT-22 — Implementar el agente | Completado |
| TIT-23 — Exponer el agente mediante MCP | Completado |
| TIT-24 — Validar con contratos SaaS | Completado |

## Comportamiento responsable

- Se procesan únicamente URL públicas proporcionadas por el usuario.
- No se realiza navegación recursiva por otros enlaces.
- No se ejecutan solicitudes masivas.
- No se intenta superar autenticación, CAPTCHA o bloqueos técnicos.
- Se conserva la URL original como fuente del contenido.
- El procesamiento se realiza con fines académicos.
- Se deben revisar las condiciones de uso de las fuentes seleccionadas.

## Limitaciones identificadas

El agente no garantiza la extracción de cualquier página web. El resultado puede depender de la estructura HTML, la disponibilidad del sitio, la autenticación, los mecanismos CAPTCHA y las condiciones de uso de cada plataforma.

## Resultado del sprint

El Sprint 2 produjo un agente Web Scraper funcional que procesa términos de servicio estáticos y dinámicos, estructura el contenido extraído y expone su funcionalidad mediante una herramienta MCP.
