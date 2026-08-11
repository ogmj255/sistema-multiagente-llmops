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
3. Si la extracción estática falla, el agente utiliza Playwright.
4. El contenido se organiza en secciones.
5. Se devuelven el texto y los metadatos del contrato.
6. Si ambos métodos fallan, se devuelve un mensaje de error.

## Validación con plataformas SaaS reales

| Plataforma | Estado | Método | Secciones | Caracteres |
|---|---|---|---:|---:|
| GitHub | Correcto | Beautiful Soup | 146 | 41483 |
| Slack | Correcto | Beautiful Soup | 26 | 12522 |
| Dropbox | Correcto | Beautiful Soup | 96 | 25318 |
| Atlassian | Correcto | Beautiful Soup | 139 | 45593 |
| HubSpot | Correcto | Beautiful Soup | 218 | 61794 |

Resultado general: cinco de cinco extracciones completadas correctamente.

## Validación del contenido dinámico

La extracción mediante Playwright se comprobó utilizando los términos de servicio de Slack.

| Campo | Resultado |
|---|---|
| Plataforma | Slack |
| Estado | Correcto |
| Método | Playwright |
| Secciones | 26 |
| Caracteres | 12522 |
| Primer encabezado | User Terms of Service |
| Primer contenido | Effective Date: February 17, 2023 |

## Pruebas complementarias

Durante el desarrollo también se realizaron pruebas con Zoom y Netflix. Ambas páginas pudieron procesarse correctamente después de mejorar la selección del contenido principal.

| Plataforma | Estado | Método |
|---|---|---|
| Zoom | Correcto | Beautiful Soup |
| Netflix | Correcto | Beautiful Soup |

En el caso de Zoom, la página contenía tres elementos `main`. El contrato estaba ubicado en el tercer elemento. El parser fue modificado para seleccionar el contenedor con mayor cantidad de texto.

## Pruebas automatizadas

Se ejecutaron trece pruebas unitarias relacionadas con:

- Validación de los esquemas del contrato.
- Endpoints principales de FastAPI.
- Extracción de HTML estático.
- Verificación de contenido suficiente.
- Eliminación de duplicados.
- Selección del contenedor principal.
- Cambio automático hacia Playwright.
- Manejo controlado cuando ambos métodos de extracción fallan.
- Exposición de la herramienta mediante MCP.

Resultado: trece pruebas aprobadas.

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
