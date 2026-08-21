# Validación de normalización de texto — TIT-27

## Objetivo

Validar la normalización de la codificación Unicode y del formato del texto obtenido desde los términos de servicio.

## Implementación

La función `normalize_text` realiza las siguientes operaciones:

- Normaliza caracteres Unicode mediante NFC.
- Elimina marcas BOM.
- Convierte espacios no separables y espacios tipográficos especiales en espacios normales.
- Normaliza tabulaciones, saltos de línea y espacios repetidos.
- Conserva tildes, eñes, puntuación, símbolos jurídicos, cantidades, monedas y enlaces.

La normalización se aplica tanto al contenido como a los encabezados durante el pipeline de limpieza.

## Decisiones técnicas

Se utiliza Unicode NFC porque conserva el significado y la representación visual del texto.

No se utiliza NFKC, traducción, conversión a minúsculas ni eliminación de acentos, debido a que estas operaciones podrían modificar nombres, símbolos o expresiones jurídicas.

## Datos representativos

Las pruebas contemplan:

- Caracteres compuestos y descompuestos.
- Texto en español con tildes y eñes.
- Espacios Unicode `U+00A0`, `U+2007` y `U+202F`.
- Tabulaciones y saltos de línea.
- Marcas BOM.
- Comillas tipográficas.
- Símbolos legales y monetarios.
- Cantidades numéricas.
- Direcciones URL con parámetros.
- Encabezados y contenido procesados dentro del pipeline completo.

## Validación automatizada

Resultado general:

- 36 pruebas unitarias aprobadas.
- Código validado mediante Ruff.
- Backend compilado correctamente.
- Sin errores bloqueantes.

Se presentó una advertencia de deprecación perteneciente a una dependencia de `TestClient`. Esta advertencia no afectó el resultado de las pruebas.

## Resultado

La implementación cumple los criterios de aceptación de TIT-27: normaliza la codificación y el formato, se verifica con datos representativos y conserva el significado del contenido contractual.
