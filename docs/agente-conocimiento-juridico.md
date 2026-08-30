# Agente de Conocimiento Jurídico

## Objetivo

Implementar un agente capaz de recuperar normativa ecuatoriana, europea e internacional mediante búsqueda semántica sobre ChromaDB.

## Responsabilidad

El agente:

1. Recibe una consulta jurídica.
2. Genera su embedding mediante Ollama.
3. Aplica filtros jurídicos opcionales.
4. Consulta la colección `legal_knowledge`.
5. Devuelve segmentos normativos con sus metadatos, fuente oficial y distancia semántica.
6. Controla errores sin interrumpir el flujo general.

El agente no genera todavía una interpretación legal mediante un LLM. Su función en este sprint es recuperar evidencia normativa trazable.

## Entrada

La consulta utiliza el esquema `KnowledgeQuery`:

```json
{
  "query": "¿Qué obligaciones existen para proteger los datos personales?",
  "top_k": 3,
  "jurisdiction": "ecuador",
  "document_type": null
}
```

Parámetros:

- `query`: consulta jurídica de al menos tres caracteres.
- `top_k`: entre 1 y 20 resultados.
- `jurisdiction`: filtro opcional.
- `document_type`: filtro opcional.

## Salida

La respuesta utiliza el esquema `KnowledgeResponse` e incluye:

- Estado de la operación.
- Consulta original.
- Segmentos recuperados.
- Identificador del documento y segmento.
- Contenido jurídico original.
- Título y organismo emisor.
- Jurisdicción y tipo documental.
- Fuente oficial.
- Cita oficial disponible.
- Distancia semántica.
- Error controlado cuando corresponda.

## Preparación del corpus

Se procesaron 51 documentos jurídicos almacenados en:

```text
data/processed/legal/
```

Resultado:

```text
Documentos preparados: 51
Segmentos generados: 7238
Identificadores únicos: 7238
Longitud máxima: 1200
Errores: 0
```

La segmentación:

- Conserva el orden original.
- Prioriza límites naturales.
- Utiliza hasta 1200 caracteres.
- Aplica hasta 200 caracteres de solapamiento.
- Mantiene metadatos jurídicos.
- Genera identificadores deterministas.

## Indexación

Los embeddings se generan mediante:

```text
qwen3-embedding:0.6b
```

Configuración:

- Dimensiones: 1024.
- Distancia: coseno.
- Tamaño de lote: 32.
- Operación de escritura: `upsert`.
- Colección: `legal_knowledge`.

Resultado registrado:

```text
Estado: success
Documentos indexados: 51
Segmentos indexados: 7238
Registros en ChromaDB: 7238
Tiempo: 1271.93 segundos
Errores: 0
```

## Prueba funcional

Consulta:

```text
¿Qué obligaciones existen para proteger los datos personales?
```

Filtro:

```text
Jurisdicción: ecuador
Resultados: 3
```

Documentos recuperados:

1. Reglamento General de la Ley Orgánica de Protección de Datos Personales.
2. Obligación de incorporar cláusulas de protección de datos en contratos celebrados en Ecuador.
3. Lineamientos y directrices de la política de privacidad y protección de datos personales.

La recuperación finalizó con estado `success` y devolvió las fuentes oficiales correspondientes.

## Ejecución reproducible

Iniciar ChromaDB:

```powershell
docker compose --env-file "backend\.env" up -d chroma
```

Preparar e indexar el corpus:

```powershell
$env:PYTHONPATH = "backend"
python "scripts\index_legal_knowledge.py"
```

Probar el agente:

```powershell
$env:PYTHONPATH = "backend"
python "scripts\test_knowledge_agent.py"
```

## Errores controlados

Se controlan:

- Consultas inválidas.
- Entradas vacías.
- Errores de Ollama.
- Embeddings con dimensiones incorrectas.
- Errores de conexión con ChromaDB.
- Colección vacía.
- Respuestas incompletas de ChromaDB.
- Errores individuales durante la preparación.
- Fallos de un lote sin detener los lotes restantes.

## Evidencias

- `backend/app/schemas/knowledge.py`
- `backend/app/services/legal_knowledge.py`
- `backend/app/services/legal_vector_store.py`
- `backend/app/agents/knowledge_agent.py`
- `scripts/index_legal_knowledge.py`
- `scripts/test_knowledge_agent.py`
- `tests/unit/test_legal_knowledge.py`
- `tests/unit/test_legal_vector_store.py`
- `tests/unit/test_knowledge_agent.py`

## Resultado

El Agente de Conocimiento Jurídico quedó operativo sobre una base vectorial persistente de 7238 segmentos procedentes de 51 documentos jurídicos. Las respuestas incluyen contenido original, metadatos y fuentes oficiales para mantener la trazabilidad.