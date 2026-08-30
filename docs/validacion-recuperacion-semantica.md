# Validación de la Recuperación Semántica de Normativa

## Objetivo

Validar el funcionamiento de la recuperación semántica implementada para el Agente de Conocimiento Jurídico, comprobando que el sistema recupere normativa pertinente, trazable y reproducible desde la colección vectorial de ChromaDB.

Esta validación corresponde a la tarea TIT-40 y utiliza el corpus jurídico previamente definido en `data/legal_sources.json`. No se construyó un benchmark artificial adicional.

## Alcance

La validación comprende:

* Preparación y segmentación del corpus jurídico.
* Generación de embeddings mediante Ollama.
* Indexación persistente en ChromaDB.
* Recuperación semántica sin filtros.
* Recuperación con filtro por jurisdicción.
* Recuperación de normativa ecuatoriana y europea.
* Eliminación de resultados exactamente duplicados.
* Ejecución mediante el servidor MCP real.
* Comprobación mediante pruebas unitarias.

El Agente de Conocimiento recupera evidencia normativa. La generación de una interpretación jurídica final y la clasificación de cláusulas abusivas corresponden a etapas posteriores del sistema multiagente.

## Conjunto de datos

Se utilizó el catálogo jurídico definido previamente en:

```text
data/legal_sources.json
```

El corpus contiene 51 fuentes jurídicas:

| Jurisdicción  | Documentos |
| ------------- | ---------: |
| Ecuador       |         30 |
| Unión Europea |         18 |
| Internacional |          3 |
| Total         |         51 |

Distribución por tipo documental:

| Tipo documental | Documentos |
| --------------- | ---------: |
| Constitución    |          1 |
| Directiva       |          9 |
| Guía            |          6 |
| Ley             |          7 |
| Reglamento      |         13 |
| Resolución      |         15 |
| Total           |         51 |

El conjunto incluye normativa relacionada con:

* Protección de consumidores.
* Contratos de adhesión.
* Cláusulas abusivas.
* Comercio electrónico.
* Servicios digitales.
* Protección de datos personales.
* Privacidad.
* Ciberseguridad.
* Plataformas digitales.
* Contratos de contenido y servicios digitales.

Por tanto, el corpus es representativo para recuperar el contexto jurídico necesario en la detección de cláusulas abusivas en términos de servicio SaaS.

## Entorno de validación

Componentes utilizados:

```text
Modelo de embeddings: qwen3-embedding:0.6b
Dimensiones: 1024
Base vectorial: ChromaDB
Colección: legal_knowledge
Métrica de distancia: coseno
Servidor de herramientas: MCP
```

La colección de ChromaDB se ejecutó mediante Docker y el modelo de embeddings mediante Ollama.

## Incidencias detectadas y correcciones

### Documento incompleto de defensa del consumidor

Durante la validación se detectó que el archivo correspondiente a la Ley Orgánica de Defensa del Consumidor contenía solamente una página y 2475 caracteres.

El documento no incluía los artículos relativos a los contratos de adhesión y las cláusulas prohibidas, por lo que la recuperación no podía devolver el artículo 43, aunque el catálogo identificaba correctamente el tema jurídico.

Se actualizó la fuente en `data/legal_sources.json` y se volvió a procesar el documento completo.

Resultado de la corrección:

```text
Páginas: 26
Caracteres extraídos: 82312
Artículo 41 encontrado: sí
Artículo 43 encontrado: sí
Contratos de adhesión encontrados: sí
```

Esta corrección permitió incorporar al corpus las nueve categorías de cláusulas prohibidas establecidas en el artículo 43.

### Cortes internos en unidades jurídicas

La segmentación inicial priorizaba saltos de línea y espacios. Esto podía provocar que algunos resultados comenzaran o terminaran en medio de una oración o disposición jurídica.

Se mejoró el algoritmo general de segmentación para priorizar:

* Artículos.
* Capítulos.
* Títulos.
* Secciones.
* Numerales.
* Finales de oración.
* Límites entre palabras.

La solución no depende de un documento específico y puede aplicarse a cualquier texto jurídico con estructuras equivalentes.

### Resultados exactamente duplicados

Durante una consulta real se detectaron dos segmentos con el mismo contenido procedentes de posiciones diferentes de un documento.

La recuperación fue ajustada para:

1. Solicitar candidatos adicionales a ChromaDB.
2. Comparar el identificador del documento y el contenido recuperado.
3. Excluir coincidencias exactamente duplicadas.
4. Conservar el orden por cercanía semántica.
5. Devolver la cantidad solicitada mediante `top_k`.

No se eliminan segmentos diferentes que pertenezcan al mismo documento, porque pueden contener disposiciones jurídicas complementarias.

## Preparación e indexación final

Después de aplicar las correcciones se reconstruyó el corpus completo.

Resultado:

```text
Documentos preparados: 51
Segmentos generados: 7238
Identificadores únicos: 7238
Longitud máxima: 1200 caracteres
Errores de preparación: 0
```

Resultado de la indexación:

```text
Estado: success
Documentos indexados: 51
Segmentos indexados: 7238
Registros en ChromaDB: 7238
Colección: legal_knowledge
Tiempo: 1271.93 segundos
Errores: 0
```

## Validación funcional mediante MCP

Las consultas se ejecutaron mediante la herramienta real `search_legal_knowledge` expuesta por el servidor MCP.

### Consulta 1: cláusulas prohibidas en Ecuador

Consulta:

```text
¿Qué cláusulas están prohibidas en los contratos de adhesión y por qué se consideran abusivas para los consumidores?
```

Parámetros:

```text
top_k: 5
jurisdiction: ecuador
document_type: sin filtro
```

Resultado:

* Estado `success`.
* Cinco coincidencias recuperadas.
* Cuatro resultados correspondientes a la Ley Orgánica de Defensa del Consumidor.
* Recuperación de los artículos 41, 43 y 44.
* Recuperación complementaria del Reglamento General a la Ley Orgánica de Telecomunicaciones.
* Distancias entre `0.36781266` y `0.40722817`.
* Cero errores bloqueantes.

El artículo 43 recuperado incluye cláusulas que:

* Limitan la responsabilidad del proveedor.
* Implican la renuncia de derechos.
* Invierten la carga de la prueba.
* Imponen arbitraje o mediación sin consentimiento expreso.
* Permiten modificar unilateralmente precios o condiciones.
* Permiten resolver unilateralmente el contrato.
* Incluyen espacios en blanco o texto ilegible.
* Implican la renuncia de derechos procesales.
* Causan indefensión al consumidor.

### Consulta 2: búsqueda global sin filtros jurídicos

Consulta:

```text
¿Qué cláusulas se consideran abusivas en los términos de servicio?
```

Parámetros:

```text
top_k: 10
jurisdiction: sin filtro
document_type: sin filtro
```

Resultado:

* Estado `success`.
* Diez coincidencias recuperadas.
* Cinco resultados de Ecuador.
* Cinco resultados de la Unión Europea.
* Distancias entre `0.5129819` y `0.56231195`.
* Cero errores bloqueantes.

Entre las fuentes recuperadas se encontraron:

* Ley Orgánica de Defensa del Consumidor.
* Reglamento General a la Ley Orgánica de Telecomunicaciones.
* Data Act.
* Directiva sobre cláusulas abusivas en contratos celebrados con consumidores.
* Digital Services Act.

La prueba confirmó que, cuando no se proporciona una jurisdicción o tipo documental, la búsqueda se realiza sobre toda la colección.

### Consulta 3: protección de datos en servicios digitales

Consulta:

```text
¿Qué obligaciones deben cumplir los proveedores de servicios digitales para proteger los datos personales de sus usuarios?
```

Parámetros:

```text
top_k: 5
jurisdiction: ecuador
document_type: sin filtro
```

Resultado:

* Estado `success`.
* Cinco coincidencias diferentes.
* Distancias entre `0.33568108` y `0.40553212`.
* Cero resultados exactamente duplicados.
* Cero errores bloqueantes.

Entre las fuentes recuperadas se encontraron:

* Reglamento General a la Ley Orgánica de Telecomunicaciones.
* Ley Orgánica para el Fortalecimiento de la Ciberseguridad.
* Reglamento General de la Ley Orgánica de Protección de Datos Personales.

Los resultados incluyeron obligaciones sobre:

* Confidencialidad, integridad y disponibilidad.
* Evaluación y gestión de riesgos.
* Políticas de seguridad.
* Controles de privacidad.
* Cumplimiento de la normativa de protección de datos.
* Medidas técnicas y organizativas.
* Garantía de los derechos de los titulares.

## Validación automatizada

Se ejecutaron las pruebas unitarias del proyecto.

Resultado:

```text
70 pruebas aprobadas
1 advertencia no bloqueante
0 pruebas fallidas
```

La advertencia corresponde a una deprecación entre Starlette y `httpx` y no afecta la funcionalidad desarrollada en TIT-40.

Las pruebas agregadas comprueban:

* Respeto de la longitud máxima de los segmentos.
* Conservación de límites jurídicos.
* Inicio de segmentos en unidades semánticas reconocibles.
* Preparación de documentos jurídicos.
* Continuidad ante errores individuales.
* Recuperación con filtros.
* Eliminación de coincidencias exactamente duplicadas.
* Control de una colección vacía.

## Evidencias

Archivos principales:

* `data/legal_sources.json`
* `backend/app/services/legal_knowledge.py`
* `backend/app/services/legal_vector_store.py`
* `backend/app/agents/knowledge_agent.py`
* `backend/app/mcp/knowledge_tools.py`
* `tests/unit/test_legal_knowledge.py`
* `tests/unit/test_legal_vector_store.py`
* `tests/unit/test_knowledge_agent.py`
* `tests/unit/test_knowledge_mcp_tools.py`
* `docs/agente-conocimiento-juridico.md`
* `docs/validacion-recuperacion-semantica.md`

## Resultado

La recuperación semántica de normativa quedó validada sobre un conjunto previamente definido de 51 documentos jurídicos y 7238 segmentos.

Las consultas realizadas mediante el servidor MCP recuperaron normativa pertinente de Ecuador y la Unión Europea, conservaron la fuente y los metadatos jurídicos, admitieron filtros opcionales y no presentaron errores bloqueantes.

También se registraron y corrigieron las incidencias relacionadas con una fuente incompleta, los cortes internos de las unidades jurídicas y la aparición de coincidencias exactamente duplicadas.

Con estas evidencias se cumplen los criterios de aceptación de TIT-40.
