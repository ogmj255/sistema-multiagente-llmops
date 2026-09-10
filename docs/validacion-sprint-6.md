# Validación final del Sprint 6 — Orquestación

## Objetivo

Al finalizar el Sprint 6 se validó la integración de los agentes mediante LangGraph y MCP, incluyendo el estado compartido, la secuencia de dependencias, la concurrencia por cláusula, los reintentos, la continuidad ante errores y el recorrido completo desde Traefik hasta la respuesta HTTP.

## Cobertura de las actividades

| Actividad | Evidencia | Resultado |
|---|---|---|
| TIT-49 — Diseñar el flujo de estados | Esquema de `OrchestrationState` y creación del estado inicial | Cumplida |
| TIT-50 — Implementar el Orquestador con LangGraph | Grafo compilado con nodos de extracción, preprocesamiento, procesamiento por cláusula y finalización | Cumplida |
| TIT-51 — Registrar herramientas y servidores MCP | Cuatro servidores registrados y descubiertos mediante sesiones MCP reales | Cumplida |
| TIT-52 — Coordinar la ejecución de agentes | Extracción → preprocesamiento → conocimiento → análisis → finalización | Cumplida |
| TIT-53 — Gestionar el estado compartido | Resultados, errores, intentos y estado general conservados en LangGraph | Cumplida |
| TIT-54 — Manejar errores y reintentos | Pruebas de agotamiento de reintentos y continuidad entre cláusulas | Cumplida |
| TIT-55 — Integrar el pipeline completo | Ejecuciones reales mediante Traefik, FastAPI, LangGraph, MCP, ChromaDB, Ollama y OpenRouter | Cumplida |
| TIT-56 — Ejecutar pruebas de integración | Pruebas reales de servidores MCP y pruebas E2E optativas | Cumplida |

## Pruebas incorporadas

### Servidores MCP reales

`tests/integration/test_mcp_servers.py` inicia cada servidor por `stdio`, establece una `ClientSession`, ejecuta la inicialización MCP y comprueba que la herramienta registrada se encuentre disponible.

Estas pruebas no simulan el transporte MCP y no realizan solicitudes al modelo legal ni a servicios externos.

Resultado obtenido:

```text
4 passed in 18.92s
```

### Pipeline de extremo a extremo

`tests/integration/test_pipeline_e2e.py` comprueba:

1. acceso a `/health` a través de Traefik;
2. rechazo HTTP 422 de una URL inválida;
3. ejecución completa de `POST /analisis` con una URL real;
4. coherencia entre cláusulas totales, analizadas, exitosas y fallidas;
5. estructura válida de los resultados clasificados o enviados a revisión humana.

Las tres pruebas E2E requieren `RUN_E2E=1`. Sin esa variable se omiten intencionalmente para que la suite cotidiana no dependa de Docker, Internet, ChromaDB, Ollama ni OpenRouter.

## Resultados obtenidos

### Suite completa en modo local de desarrollo

```text
135 passed, 3 skipped in 22.00s
```

Los tres casos omitidos corresponden exclusivamente a las pruebas E2E optativas.

### Pruebas específicas del orquestador

Se verificaron la coordinación mediante MCP, el límite de cinco cláusulas concurrentes, el agotamiento de reintentos y la continuidad después de errores de conocimiento o análisis.

```text
5 passed, 2 deselected in 5.34s
```

También se comprobó mediante búsqueda estática que el orquestador no invoque directamente funciones internas de los agentes. Las cuatro capacidades se llaman mediante `ClienteMCP.invocar`.

### E2E breve con `example.com`

```text
E2E_DURATION_SECONDS=28.20
3 passed in 29.78s
```

Los registros mostraron una respuesta HTTP 422 esperada para el caso inválido, una respuesta HTTP 200 para el recorrido completo y seis invocaciones MCP:

- una extracción;
- un preprocesamiento;
- dos recuperaciones jurídicas;
- dos análisis legales.

### E2E real con Seed4

URL validada: `https://seed4.me/pages/terms`

```text
E2E_DURATION_SECONDS=202.51
1 passed, 2 deselected in 202.83s
```

La ejecución procesó 32 cláusulas y produjo exactamente 66 invocaciones MCP:

```text
1 extracción + 1 preprocesamiento + 32 consultas jurídicas + 32 análisis legales = 66
```

El endpoint respondió HTTP 200 y los registros filtrados no mostraron `ERROR` ni `Traceback`. La ausencia de llamadas adicionales también indica que esta ejecución no necesitó reintentos.

## Evaluación de rendimiento

| Ejecución Seed4 | Duración | Observación |
|---|---:|---|
| Flujo secuencial anterior | 1491.80 s | Referencia previa a la concurrencia |
| Primera validación concurrente | 418.96 s | Máximo de cinco cláusulas activas |
| Validación actual | 202.51 s | Pipeline actual y prueba E2E aprobada |

Frente a la referencia secuencial, la validación actual fue aproximadamente **7.37 veces más rápida** y redujo el tiempo en **86.43 %**.

La comparación mide ejecuciones reales, pero no constituye todavía un benchmark controlado: la latencia de la página de origen, Ollama y OpenRouter puede variar. Para obtener métricas estadísticas deberán repetirse varias ejecuciones bajo las mismas condiciones en un sprint de evaluación.

## Comandos de reproducción

Pruebas unitarias y de integración que no necesitan servicios externos:

```powershell
python -m ruff check backend tests

python -m pytest -q `
    -o pythonpath=backend
```

E2E real con los contenedores en ejecución:

```powershell
$env:RUN_E2E = "1"
$env:E2E_BASE_URL = "http://127.0.0.1"
$env:E2E_TERMS_URL = "https://example.com"
$env:E2E_TIMEOUT_SECONDS = "600"

python -m pytest -q -s `
    -o pythonpath=backend `
    "tests\integration\test_pipeline_e2e.py"

Remove-Item Env:\RUN_E2E -ErrorAction SilentlyContinue
Remove-Item Env:\E2E_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:\E2E_TERMS_URL -ErrorAction SilentlyContinue
Remove-Item Env:\E2E_TIMEOUT_SECONDS -ErrorAction SilentlyContinue
```

## Conclusión

El pipeline de extremo a extremo está integrado y las pruebas demuestran que LangGraph controla el flujo, que los agentes se invocan mediante MCP, que las dependencias de cada cláusula conservan su orden, que la concurrencia se limita a cinco tareas y que una falla aislada no detiene las demás cláusulas.

Con esta evidencia, TIT-55 y TIT-56 pueden marcarse como finalizadas y el Sprint 6 queda técnicamente listo para su cierre.
