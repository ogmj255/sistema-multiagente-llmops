# Fuentes y criterios de selección de normativa

## Fecha de definición

24 de agosto de 2026.

## Objetivo

Definir las fuentes oficiales y los criterios para seleccionar los documentos jurídicos que formarán la base de conocimiento del Agente de Conocimiento.

El corpus estará compuesto por normativa ecuatoriana e internacional relacionada con los términos de servicio de plataformas SaaS.

## Alcance

La base jurídica incluirá documentos relacionados con:

- Protección de datos personales y privacidad.
- Derechos de los consumidores.
- Contratación electrónica.
- Firmas electrónicas y mensajes de datos.
- Servicios y plataformas digitales.
- Cláusulas contractuales y condiciones abusivas.
- Propiedad intelectual y licenciamiento digital.
- Seguridad de la información y notificación de incidentes.
- Transferencias internacionales de datos.
- Jurisdicción y mecanismos de resolución de controversias.

Los ToS de las plataformas no forman parte de la normativa. Son los documentos que posteriormente serán contrastados con la base jurídica.

## Fuentes ecuatorianas

| Fuente | Contenido aceptado |
|---|---|
| [Registro Oficial](https://www.registroficial.gob.ec/) | Leyes, reglamentos, decretos y resoluciones publicadas oficialmente |
| [Asamblea Nacional](https://www.asambleanacional.gob.ec/es/leyes-aprobadas) | Constitución, leyes aprobadas y referencias al Registro Oficial |
| [Superintendencia de Protección de Datos Personales](https://spdp.gob.ec/) | Resoluciones, normas, circulares y guías oficiales |
| [Corte Constitucional](https://www.corteconstitucional.gob.ec/) | Jurisprudencia vinculante relacionada con derechos digitales |
| [Defensoría del Pueblo](https://www.dpe.gob.ec/) | Resoluciones y documentos oficiales sobre consumidores y derechos fundamentales |
| [ARCOTEL](https://www.arcotel.gob.ec/) | Regulaciones aplicables a telecomunicaciones y servicios digitales |

El Registro Oficial tendrá prioridad cuando existan distintas versiones de una misma norma. La Asamblea Nacional publica leyes aprobadas junto con su referencia de publicación oficial, mientras que la SPDP mantiene resoluciones y guías especializadas en protección de datos.

## Fuentes internacionales

| Fuente | Contenido aceptado |
|---|---|
| [EUR-Lex](https://eur-lex.europa.eu/) | Reglamentos y directivas de la Unión Europea |
| [UNCTAD](https://unctad.org/topic/competition-and-consumer-protection/un-guidelines-for-consumer-protection) | Directrices de Naciones Unidas sobre protección al consumidor |
| [OCDE](https://www.oecd.org/en/topics/privacy-and-data-protection.html) | Directrices sobre privacidad, seguridad digital y comercio electrónico |
| [Consejo de Europa](https://www.coe.int/en/web/data-protection/convention108-and-protocol) | Convenio 108 y documentos oficiales de protección de datos |

Entre los documentos internacionales prioritarios se consideran:

- Reglamento General de Protección de Datos de la Unión Europea.
- Digital Services Act.
- Directiva sobre contratos de suministro de contenidos y servicios digitales.
- Directiva sobre cláusulas abusivas en contratos con consumidores.
- Directrices de Naciones Unidas para la protección del consumidor.
- Directrices de privacidad y comercio electrónico de la OCDE.
- Convenio 108 y sus protocolos.

## Composición mínima del corpus

El entregable debe contener al menos 50 documentos jurídicos:

- Mínimo 30 documentos ecuatorianos.
- Mínimo 20 documentos internacionales.

Cada ley, reglamento, resolución, directiva o instrumento oficial contará como un documento. No se contarán artículos o fragmentos de una misma norma como documentos independientes.

## Criterios obligatorios de selección

Un documento será aceptado cuando cumpla todos los criterios siguientes:

1. Procede de una institución pública u organización internacional oficial.
2. Tiene relación directa con una de las áreas jurídicas definidas.
3. Su contenido completo está disponible.
4. Su versión y fecha pueden identificarse.
5. Su procedencia puede verificarse mediante una URL oficial.
6. No duplica otro documento incorporado.
7. Puede convertirse a texto para su posterior procesamiento.
8. Su idioma está identificado.
9. Su estado jurídico puede clasificarse.

## Vigencia

Se priorizarán documentos vigentes y versiones consolidadas.

Los documentos derogados, sustituidos o históricos no ingresarán al corpus inicial, excepto cuando posteriormente se necesiten para analizar ToS correspondientes a una fecha anterior.

Los proyectos de ley o proyectos normativos serán excluidos porque todavía no constituyen normativa vigente.

## Clasificación jurídica

Cada documento deberá clasificarse como:

- Normativa vinculante.
- Jurisprudencia vinculante.
- Directriz o instrumento internacional.
- Guía oficial no vinculante.

Esta clasificación evitará presentar una recomendación o guía como si tuviera la misma fuerza jurídica que una ley.

## Metadatos requeridos

Cada documento deberá almacenar:

| Campo | Descripción |
|---|---|
| `document_id` | Identificador único |
| `title` | Título oficial |
| `jurisdiction` | Ecuador, Unión Europea o internacional |
| `issuing_body` | Institución emisora |
| `document_type` | Ley, reglamento, resolución, directiva, convenio o guía |
| `binding_level` | Vinculante, jurisprudencial o referencial |
| `status` | Vigente, reformado, derogado o no determinado |
| `publication_date` | Fecha de publicación |
| `effective_date` | Fecha de entrada en vigor, cuando esté disponible |
| `language` | Idioma del documento |
| `official_citation` | Número de Registro Oficial, resolución o identificación equivalente |
| `source_url` | URL oficial |
| `retrieved_at` | Fecha de recuperación |
| `topics` | Materias jurídicas asociadas |
| `checksum` | Huella para verificar integridad y detectar duplicados |

## Entradas

La actividad de recopilación recibirá:

- URL oficial.
- Institución emisora.
- Tipo de documento.
- Jurisdicción.
- Materia jurídica.
- Archivo HTML o PDF disponible.

## Salidas

La recopilación producirá:

- Documento jurídico original.
- Texto extraído y normalizado.
- Metadatos estructurados.
- Estado de aceptación o rechazo.
- Motivo de rechazo, cuando corresponda.
- Documento preparado para segmentación y generación de embeddings.

## Motivos de rechazo

Se rechazará un documento cuando:

- Provenga de blogs, Wikipedia, medios de comunicación o estudios jurídicos.
- Sea un resumen no oficial.
- No pueda verificarse su procedencia.
- Esté duplicado.
- No tenga relación con el alcance jurídico.
- Sea únicamente un proyecto normativo.
- Esté incompleto o dañado.
- No permita determinar su identidad o versión.

## Decisiones principales

- Se utilizarán únicamente fuentes oficiales.
- Ecuador será la jurisdicción principal.
- La normativa internacional se utilizará para comparación y referencia.
- Se diferenciará entre instrumentos vinculantes y no vinculantes.
- ChromaDB almacenará fragmentos, embeddings y metadatos.
- El documento original se conservará para garantizar trazabilidad.
- La cantidad de documentos no tendrá prioridad sobre su calidad y relevancia.
- La selección no constituye asesoría legal.