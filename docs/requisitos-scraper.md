# Requisitos del agente Web Scraper

## Objetivo

Desarrollar un agente que permita obtener el contenido textual de los términos de servicio publicados en sitios web de plataformas SaaS. El agente deberá conservar el orden y la estructura básica del documento para facilitar su procesamiento posterior.

## Alcance

El agente realizará la extracción y organización del contrato. La limpieza avanzada, segmentación, clasificación de cláusulas y análisis con modelos de lenguaje se implementarán en los siguientes sprints.

## Fuentes iniciales

| Plataforma | Dirección |
|---|---|
| GitHub | https://docs.github.com/site-policy/github-terms/github-terms-of-service |
| Dropbox | https://www.dropbox.com/terms |
| Slack | https://slack.com/terms-of-service/user |
| Atlassian | https://www.atlassian.com/legal/atlassian-customer-agreement |
| HubSpot | https://legal.hubspot.com/terms-of-service |

Estas fuentes fueron seleccionadas porque presentan términos de servicio públicos, extensos y organizados mediante HTML.

## Requisitos de entrada

El agente recibirá:

- Una dirección web mediante una URL.
- La URL deberá utilizar el protocolo HTTP o HTTPS.
- La dirección deberá corresponder a una página pública.
- No se procesarán páginas que requieran usuario y contraseña.

## Requisitos de extracción

El agente deberá:

1. Validar que la URL tenga un formato correcto.
2. Comprobar que la página pueda ser consultada.
3. Extraer el título del documento.
4. Extraer encabezados, párrafos y listas.
5. Conservar el orden original del contenido.
6. Registrar la URL de origen.
7. Registrar la fecha y hora de extracción.
8. Identificar el método utilizado para la extracción.
9. Excluir únicamente elementos técnicos no visibles, como scripts y estilos, conservando el texto visible para su posterior preprocesamiento.
10. Informar de manera comprensible cuando la extracción no pueda realizarse.

## Métodos de extracción

| Método | Uso |
|---|---|
| Beautiful Soup | Páginas cuyo contenido se encuentra directamente en el HTML |
| Playwright | Páginas cuyo contenido se carga mediante JavaScript |

Se intentará primero la extracción con Beautiful Soup. Playwright se utilizará únicamente cuando el contenido no pueda obtenerse mediante una solicitud HTTP normal.

## Estructura de salida

| Campo | Descripción |
|---|---|
| `source_url` | Dirección original del contrato |
| `platform` | Nombre de la plataforma |
| `title` | Título del documento |
| `retrieved_at` | Fecha y hora de extracción |
| `extraction_method` | Método utilizado |
| `language` | Idioma identificado |
| `sections` | Secciones con encabezado y contenido |
| `full_text` | Texto completo extraído |
| `status` | Resultado de la extracción |
| `error` | Descripción del error, cuando corresponda |

## Requisitos de comportamiento responsable

- Procesar únicamente URL públicas proporcionadas por el usuario.
- No recorrer automáticamente otros enlaces del sitio web.
- No realizar solicitudes masivas o repetitivas.
- No intentar superar autenticación, CAPTCHA o bloqueos técnicos.
- Revisar las condiciones de uso de las fuentes seleccionadas para la evaluación.
- Registrar siempre la fuente del contenido.
- Utilizar el contenido únicamente con fines académicos.

## Criterios de aceptación

- Se encuentran documentadas al menos cinco fuentes de prueba.
- Están definidos los datos de entrada y salida.
- Se diferencia el uso de Beautiful Soup y Playwright.
- Se establecen reglas básicas para una extracción responsable.
- La estructura de salida permite conservar la fuente y el contenido del contrato.
- El alcance se limita a la extracción, sin incluir todavía el análisis de cláusulas.

## Resultado esperado

Al finalizar el desarrollo del agente, el sistema podrá recibir una URL pública y devolver el contrato organizado junto con sus metadatos. Esta salida servirá como entrada para el preprocesamiento y la construcción del índice del documento.
