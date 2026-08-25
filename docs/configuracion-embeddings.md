# Configuración del modelo de embeddings

## Objetivo

Configurar un modelo local y reproducible para generar los vectores utilizados por la Base de Conocimiento Jurídico del Sprint 4.

## Modelo seleccionado

Se utiliza `qwen3-embedding:0.6b` mediante Ollama.

Características principales:

- Modelo especializado en generación de embeddings.
- Tamaño aproximado de 639 MB.
- Vectores de 1024 dimensiones.
- Soporte para más de 100 idiomas.
- Compatible con documentos jurídicos en español e inglés.
- Ejecución local sin depender de una API externa.

Fuentes oficiales:

- https://ollama.com/library/qwen3-embedding:0.6b
- https://docs.ollama.com/capabilities/embeddings

## Arquitectura

El backend envía uno o varios textos al endpoint `/api/embed` de Ollama. El servicio valida la respuesta y devuelve un vector de 1024 dimensiones por cada texto.

Los vectores serán almacenados posteriormente en ChromaDB durante la indexación del corpus jurídico.

## Variables de entorno

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
OLLAMA_EMBEDDING_DIMENSIONS=1024
```

Cuando el backend se ejecuta dentro de Docker utiliza:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Instalación reproducible

```powershell
ollama pull qwen3-embedding:0.6b
ollama list
```

## Prueba funcional

Desde la raíz del proyecto:

```powershell
$env:PYTHONPATH = "backend"
python "scripts\test_embeddings.py"
```

Resultado registrado:

```text
Servidor: http://localhost:11434
Modelo: qwen3-embedding:0.6b
Textos procesados: 2
Vectores generados: 2
Dimensiones: 1024
Estado: success
```

## Controles implementados

El servicio controla:

- Entradas vacías.
- Errores de conexión con Ollama.
- Respuestas sin embeddings.
- Cantidad inesperada de vectores.
- Dimensiones diferentes de 1024.
- Valores no numéricos en los vectores.

## Evidencias

- `backend/app/services/embeddings.py`
- `tests/unit/test_embeddings.py`
- `scripts/test_embeddings.py`
- `backend/app/core/config.py`
- `backend/.env.example`
- `docker-compose.yaml`

## Resultado

El modelo quedó configurado y operativo. La generación individual y por lotes funciona sin errores bloqueantes y produce vectores consistentes de 1024 dimensiones.