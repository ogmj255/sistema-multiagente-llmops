# Sistema multiagente con enfoque LLMOps para la detección de cláusulas potencialmente abusivas

## Descripción

Proyecto de titulación orientado al desarrollo de un sistema multiagente que utiliza modelos de lenguaje generativos y prácticas LLMOps para analizar términos de servicio de plataformas SaaS/PaaS e identificar cláusulas potencialmente abusivas.

## Objetivo

Desarrollar un prototipo web capaz de obtener, procesar y analizar contratos digitales mediante agentes especializados, proporcionando resultados justificables, trazables y evaluables.

## Arquitectura

El sistema adopta una arquitectura de monolito modular contenedorizado, separada en los siguientes componentes:

- **Back-end:** FastAPI y Pydantic.
- **Orquestación multiagente:** LangGraph.
- **Interfaz web:** Streamlit.
- **Modelo local:** Ollama con qwen3:4b.
- **Persistencia:** PostgreSQL y SQLAlchemy.
- **Extracción:** Beautiful Soup y Playwright.
- **Integración de herramientas:** Model Context Protocol (MCP).
- **Observabilidad LLMOps:** Langfuse.
- **Infraestructura:** Docker Compose y Traefik.
- **Pruebas:** pytest.

## Clasificación binaria y evaluación experimental (V2 en desarrollo)

La versión experimental V2 distingue exclusivamente dos clases de riesgo:
**NPA** (no potencialmente abusiva) y **PA** (potencialmente abusiva).
La aplicabilidad se comprueba por separado, y los fragmentos no evaluables
se registran como `not_applicable`, sin elevarlos a tercera clase jurídica.

La interfaz Streamlit incorpora **Evaluación experimental**, con selección
de documento, modelo y repetición, una API protegida y un worker MCP
independiente. La ejecución de pago está deshabilitada por defecto.
La referencia histórica V1 y los primeros ensayos se conservan aislados.

Consultar: [Protocolo V2 y seguridad](docs/protocolo-binario-v2-interfaz.md).

## Estructura del repositorio

- `backend/`: API, agentes, servicios e integraciones.
- `frontend/`: interfaz web del sistema.
- `tests/`: pruebas unitarias y de integración.
- `data/`: datos originales, procesados y de evaluación.
- `infra/`: configuración de contenedores y API Gateway.
- `docs/`: documentación técnica y académica.
- `scripts/`: utilidades para desarrollo y evaluación.

## Metodología de desarrollo

El desarrollo se gestiona mediante Scrum, utilizando Jira para la planificación de sprints y GitHub para el control de versiones.

## Autor

Omar Moscoso
