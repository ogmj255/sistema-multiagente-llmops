# Servidor MCP del Agente de Conocimiento

## Objetivo

Exponer las capacidades del Agente de Conocimiento Jurídico mediante un servidor Model Context Protocol (MCP), permitiendo realizar consultas semánticas sobre la base normativa desde clientes compatibles.

## Arquitectura

El flujo de ejecución es:

1. El cliente MCP envía una consulta.
2. FastMCP valida los parámetros recibidos.
3. La herramienta construye un objeto `KnowledgeQuery`.
4. El agente genera el embedding mediante Ollama.
5. El agente consulta la colección `legal_knowledge` en ChromaDB.
6. El servidor devuelve una respuesta estructurada con contenido, metadatos y fuentes oficiales.

## Servidor

El servidor está implementado en:

```text
backend/app/mcp/knowledge_tools.py
```

Nombre del servidor:

```text
Agente de Conocimiento Jurídico
```

Transporte utilizado:

```text
stdio
```

## Herramienta disponible

Nombre:

```text
search_legal_knowledge
```

Responsabilidad:

```text
Recuperar normativa relevante desde la base jurídica.
```

## Entrada

La herramienta recibe:

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
- `top_k`: cantidad de resultados, entre 1 y 20.
- `jurisdiction`: jurisdicción opcional.
- `document_type`: tipo documental opcional.

## Salida

La herramienta devuelve:

- Estado de la operación.
- Consulta original.
- Segmentos jurídicos recuperados.
- Identificador del documento y segmento.
- Contenido original.
- Título y organismo emisor.
- Jurisdicción y tipo documental.
- Fuente oficial.
- Cita oficial.
- Fechas disponibles.
- Temas jurídicos.
- Distancia semántica.
- Mensaje de error cuando corresponda.

## Ejecución no bloqueante

El Agente de Conocimiento realiza operaciones síncronas de red con Ollama y ChromaDB. Para evitar bloquear el bucle asíncrono del servidor MCP, la herramienta ejecuta el agente mediante:

```python
await asyncio.to_thread(...)
```

Esto permite conservar una interfaz MCP asíncrona mientras la recuperación jurídica se realiza en un hilo separado.

## Control de errores

Se controlan los siguientes casos:

- Consultas inválidas.
- Cantidad de resultados fuera del rango permitido.
- Jurisdicciones o tipos documentales no admitidos.
- Errores de generación de embeddings.
- Errores de conexión con Ollama.
- Errores de conexión con ChromaDB.
- Colección jurídica vacía.
- Respuestas incompletas de la base vectorial.
- Errores controlados devueltos por el agente.

Los errores operativos se devuelven dentro de una respuesta estructurada sin interrumpir el flujo completo.

## Pruebas unitarias

Las pruebas están implementadas en:

```text
tests/unit/test_knowledge_mcp_tools.py
```

Se verificó:

1. La recepción y validación de los parámetros.
2. La construcción correcta de `KnowledgeQuery`.
3. La ejecución del Agente de Conocimiento.
4. La serialización de los resultados.
5. La conservación de errores controlados.

Resultado:

```text
2 pruebas aprobadas.
```

## Prueba de integración MCP

La prueba está implementada en:

```text
scripts/test_knowledge_mcp.py
```

El script:

1. Inicia el servidor como un subproceso.
2. Establece una conexión MCP mediante `stdio`.
3. Inicializa la sesión.
4. Solicita la lista de herramientas.
5. Verifica la existencia de `search_legal_knowledge`.
6. Ejecuta una consulta contra Ollama y ChromaDB.
7. Comprueba que la respuesta no contenga un error MCP.

Consulta utilizada:

```text
¿Qué obligaciones existen para proteger los datos personales?
```

Configuración:

```text
top_k: 3
jurisdiction: ecuador
```

Resultado:

```text
Herramientas: ['search_legal_knowledge']
Error MCP: False
Estado: success
Resultados: 3
```

Documentos recuperados:

1. Reglamento General de la Ley Orgánica de Protección de Datos Personales.
2. Obligación de incorporar cláusulas de protección de datos en contratos celebrados en Ecuador.
3. Lineamientos y directrices de la política de privacidad y protección de datos personales.

## Ejecución reproducible

Iniciar ChromaDB:

```powershell
docker compose --env-file "backend\.env" up -d chroma
```

Comprobar los modelos de Ollama:

```powershell
ollama list
```

Configurar la ruta del backend:

```powershell
$env:PYTHONPATH = "backend"
```

Ejecutar el servidor directamente:

```powershell
python -m app.mcp.knowledge_tools
```

Ejecutar la prueba de integración:

```powershell
python "scripts\test_knowledge_mcp.py"
```

## Evidencias

- `backend/app/mcp/knowledge_tools.py`
- `tests/unit/test_knowledge_mcp_tools.py`
- `scripts/test_knowledge_mcp.py`
- `docs/servidor-mcp-conocimiento.md`

## Resultado

El servidor MCP del Agente de Conocimiento quedó operativo. La herramienta puede descubrirse y ejecutarse mediante el protocolo MCP, realiza consultas reales sobre la base jurídica y devuelve normativa con metadatos y fuentes oficiales.