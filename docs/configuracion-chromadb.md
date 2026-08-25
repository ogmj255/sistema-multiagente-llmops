# Configuración de ChromaDB

## Objetivo

Configurar ChromaDB como base vectorial persistente para la Base de Conocimiento Jurídico del Sprint 4.

## Arquitectura

ChromaDB funciona en modo cliente-servidor:

- Servidor: contenedor Docker.
- Cliente: paquete Python `chromadb-client`.
- Persistencia: volumen Docker `chroma_data`.
- Acceso desde Windows: `localhost:8001`.
- Acceso desde el backend: `chroma:8000`.
- Colección jurídica: `legal_knowledge`.

## Versiones

- Servidor ChromaDB: `1.5.9`.
- Cliente Python: `1.5.9`.

## Variables de entorno

- `CHROMA_HOST=localhost`
- `CHROMA_PORT=8001`
- `CHROMA_COLLECTION=legal_knowledge`

Docker Compose reemplaza el host y puerto por `chroma:8000` dentro del backend.

## Pasos reproducibles

1. Crear `backend/.env` a partir de `backend/.env.example`.
2. Instalar las dependencias de `backend/requirements.txt`.
3. Iniciar ChromaDB:

   `docker compose --env-file backend/.env up -d chroma`

4. Comprobar el contenedor:

   `docker compose --env-file backend/.env ps chroma`

5. Ejecutar la prueba funcional:

   `$env:PYTHONPATH = "backend"`

   `python scripts/test_chromadb.py`

## Prueba funcional

La prueba realiza:

1. Conexión mediante `HttpClient`.
2. Verificación del heartbeat.
3. Creación de una colección temporal.
4. Escritura de un vector.
5. Consulta por similitud.
6. Validación del resultado.
7. Eliminación de la colección temporal.

Resultado esperado:

- `Resultado: configuration_vector`
- `Estado: success`

## Persistencia

Los datos se almacenan en el volumen Docker `chroma_data`. El comando `docker compose stop chroma` detiene el servicio sin eliminar la información.

## Evidencia

ChromaDB inició mediante Docker, respondió al heartbeat y permitió almacenar y recuperar un vector sin errores bloqueantes.

## Referencia

Documentación oficial: https://docs.trychroma.com/guides/deploy/docker