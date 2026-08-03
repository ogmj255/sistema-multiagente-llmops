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

## Estado

En desarrollo — Sprint 1: Estructura base del sistema.

## Autor

Omar Moscoso
