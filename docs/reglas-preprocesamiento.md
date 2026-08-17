# Reglas de limpieza y segmentación semántica

## Objetivo

Definir las reglas que utilizará el agente preprocesador para limpiar el contenido obtenido por el Web Scraper y dividirlo en cláusulas con significado completo.

## Entrada

El preprocesador recibirá:

- URL de origen.
- Nombre de la plataforma.
- Título del documento.
- Idioma.
- Secciones extraídas.
- Texto completo.

## Reglas de limpieza

1. Eliminar contenido vacío.
2. Eliminar duplicados exactos consecutivos.
3. Eliminar menús de navegación.
4. Eliminar botones y enlaces de interfaz.
5. Eliminar avisos de cookies.
6. Eliminar pies de página que no pertenezcan al contrato.
7. Eliminar referencias a imágenes o tablas que no contengan información legal.
8. Eliminar espacios repetidos.
9. Corregir saltos de línea innecesarios.
10. Reemplazar espacios especiales por espacios normales.

La limpieza no deberá cambiar el significado del contenido legal.

## Contenido que debe conservarse

Se conservarán:

- Títulos y subtítulos.
- Numeración de cláusulas.
- Párrafos.
- Listas.
- Fechas de vigencia.
- Cantidades y valores monetarios.
- Referencias legales.
- Enlaces que formen parte del contrato.
- Orden original del contenido.

## Reglas de segmentación semántica

1. Cada cláusula deberá expresar una idea legal comprensible.
2. Los encabezados marcarán el inicio de una sección.
3. La numeración como `1.`, `1.1`, `A.` o `a)` ayudará a identificar cláusulas.
4. Los párrafos se asociarán con el encabezado más cercano.
5. Los elementos de una lista conservarán su relación con la cláusula principal.
6. Una oración no se dividirá por la mitad.
7. Los párrafos relacionados con la misma obligación o derecho podrán mantenerse juntos.
8. Un párrafo con varias ideas legales independientes podrá separarse en más de una cláusula.
9. No se dividirá el texto por una cantidad fija de palabras, caracteres o tokens.
10. Las cláusulas conservarán el orden del documento original.

## Salida esperada

El resultado se representará en formato JSON.

```json
{
  "source_url": "https://example.com/terms",
  "platform": "Example",
  "title": "Terms of Service",
  "clauses": [
    {
      "order": 1,
      "heading": "1. Account Terms",
      "content": "The user must provide accurate information."
    }
  ]
}
```

## Ejemplos de verificación

### GitHub

Los textos de navegación se eliminarán. Los encabezados y las condiciones relacionadas con las cuentas se conservarán como cláusulas.

### Slack

Los enlaces de productos y navegación se eliminarán. La fecha de vigencia, los encabezados y las condiciones de uso se conservarán.

### Dropbox

Los elementos del pie de página se eliminarán. Los títulos, párrafos y listas pertenecientes a los términos de servicio se conservarán.

## Fuera del alcance

En esta etapa no se realizará:

- Traducción.
- Resumen.
- Clasificación de cláusulas.
- Detección de cláusulas abusivas.
- Creación del índice Vectorless.
- Generación del informe final.

Estas actividades corresponden a sprints posteriores.
