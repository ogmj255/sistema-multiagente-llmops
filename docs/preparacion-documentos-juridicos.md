# Preparación de documentos jurídicos y metadatos

## Objetivo

Definir cómo se transformará el corpus jurídico procesado en unidades uniformes listas para generar embeddings y almacenarse posteriormente en ChromaDB.

## Alcance

La preparación incluye:

- Validación de los documentos procesados.
- Conservación del contenido jurídico original.
- Segmentación del texto en unidades recuperables.
- Asociación de cada segmento con sus metadatos.
- Generación de identificadores únicos y reproducibles.

No incluye:

- Generación de embeddings.
- Carga en ChromaDB.
- Recuperación semántica.
- Generación de respuestas mediante un LLM.

## Entrada

Los documentos generados por el constructor del corpus y almacenados en:

`data/processed/legal/`

Cada documento contiene:

- Fuente jurídica.
- URL oficial.
- Jurisdicción.
- Organismo emisor.
- Tipo y estado del documento.
- Nivel de obligatoriedad.
- Idioma.
- Temas jurídicos.
- Fechas disponibles.
- Checksum.
- Texto extraído.

## Salida prevista

La preparación producirá un archivo JSONL en:

`data/processed/legal_chunks.jsonl`

Cada línea representará un segmento jurídico listo para generar su embedding.

## Estructura del segmento

| Campo | Descripción |
|---|---|
| `chunk_id` | Identificador único y determinista |
| `document_id` | Identificador del documento de origen |
| `chunk_index` | Posición del segmento dentro del documento |
| `content` | Texto jurídico conservado |
| `title` | Título del documento |
| `jurisdiction` | Jurisdicción aplicable |
| `issuing_body` | Organismo emisor |
| `document_type` | Tipo de documento jurídico |
| `binding_level` | Nivel de obligatoriedad |
| `status` | Estado de vigencia |
| `language` | Idioma |
| `source_url` | Fuente oficial |
| `official_citation` | Cita oficial disponible |
| `publication_date` | Fecha de publicación |
| `effective_date` | Fecha de vigencia |
| `topics` | Temas jurídicos asociados |
| `checksum` | Huella del documento original |

## Reglas de preparación

1. Procesar únicamente documentos con contenido no vacío.
2. Conservar el orden original del texto.
3. No resumir, traducir ni reformular el contenido jurídico.
4. Priorizar límites de párrafo durante la segmentación.
5. Utilizar segmentos de hasta 1200 caracteres.
6. Aplicar un solapamiento máximo de 200 caracteres cuando sea necesario dividir un bloque extenso.
7. Evitar segmentos vacíos o duplicados.
8. Generar identificadores con el formato:

   `{document_id}_chunk_{chunk_index:04d}`

9. Mantener los metadatos del documento en todos sus segmentos.
10. Representar fechas mediante el formato ISO 8601.
11. Representar `topics` como texto separado por barras verticales para mantener compatibilidad con los metadatos escalares de ChromaDB.

## Decisiones principales

- La base jurídica utilizará segmentación tradicional porque será recuperada mediante embeddings y ChromaDB.
- El procesamiento Vectorless de los términos de servicio permanece separado de esta base de conocimiento.
- La preparación no modificará el significado ni la redacción de la normativa.
- Los identificadores serán deterministas para permitir reconstruir la base sin crear duplicados.
- Los documentos sin texto utilizable serán registrados como errores y no bloquearán el procesamiento completo.

## Validaciones

La preparación deberá comprobar:

- Al menos 50 documentos jurídicos de origen.
- Al menos un segmento por documento.
- Identificadores únicos.
- Segmentos no vacíos.
- Conservación del orden.
- Presencia de la URL oficial y checksum.
- Correspondencia entre segmentos y documentos originales.

## Flujo posterior

Los segmentos preparados serán utilizados por las siguientes actividades del Sprint 4 para:

1. Generar embeddings.
2. Cargar la colección jurídica en ChromaDB.
3. Implementar el Agente de Conocimiento.
4. Ejecutar pruebas de recuperación semántica.