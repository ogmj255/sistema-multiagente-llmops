import re
from math import floor, sqrt

from app.services.embeddings import generate_embeddings

SENTENCE_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?])\s+|\n{2,}"
)


def cosine_distance(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """Calcula la distancia coseno entre dos vectores."""

    if not vector_a or not vector_b:
        raise ValueError(
            "Los vectores no pueden estar vacios."
        )

    if len(vector_a) != len(vector_b):
        raise ValueError(
            "Los vectores deben tener la misma dimension."
        )

    dot_product = sum(
        value_a * value_b
        for value_a, value_b in zip(
            vector_a,
            vector_b,
            strict=True,
        )
    )

    norm_a = sqrt(
        sum(value * value for value in vector_a)
    )
    norm_b = sqrt(
        sum(value * value for value in vector_b)
    )

    if norm_a == 0 or norm_b == 0:
        raise ValueError(
            "No se puede usar un vector nulo."
        )

    similarity = dot_product / (
        norm_a * norm_b
    )

    return 1.0 - similarity


def _split_long_sentence(
    text: str,
    max_chars: int,
) -> list[str]:
    """Divide texto excepcionalmente largo por palabras."""

    if len(text) <= max_chars:
        return [text]

    words = text.split()

    if not words:
        return []

    parts: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(
            current + [word]
        )

        if current and len(candidate) > max_chars:
            parts.append(
                " ".join(current)
            )
            current = [word]
        else:
            current.append(word)

    if current:
        parts.append(
            " ".join(current)
        )

    return parts


def split_into_sentences(
    text: str,
    *,
    max_sentence_chars: int = 3500,
) -> list[str]:
    """Separa el texto limpio en unidades oracionales."""

    if max_sentence_chars <= 0:
        raise ValueError(
            "max_sentence_chars debe ser mayor que cero."
        )

    normalized = text.strip()

    if not normalized:
        return []

    raw_sentences = SENTENCE_SPLIT_PATTERN.split(
        normalized
    )

    sentences: list[str] = []

    for sentence in raw_sentences:
        clean = " ".join(
            sentence.split()
        )

        if not clean:
            continue

        sentences.extend(
            _split_long_sentence(
                clean,
                max_sentence_chars,
            )
        )

    return sentences


def build_context_groups(
    sentences: list[str],
    *,
    buffer_size: int = 1,
) -> list[str]:
    """Combina oraciones vecinas para obtener contexto."""

    if buffer_size < 0:
        raise ValueError(
            "buffer_size no puede ser negativo."
        )

    groups: list[str] = []

    for index in range(len(sentences)):
        start = max(
            0,
            index - buffer_size,
        )
        end = min(
            len(sentences),
            index + buffer_size + 1,
        )

        groups.append(
            " ".join(
                sentences[start:end]
            )
        )

    return groups


def calculate_semantic_distances(
    sentences: list[str],
    *,
    buffer_size: int = 1,
) -> list[float]:
    """Calcula distancias entre grupos adyacentes."""

    if len(sentences) < 2:
        return []

    groups = build_context_groups(
        sentences,
        buffer_size=buffer_size,
    )

    embeddings = generate_embeddings(
        groups
    )

    if len(embeddings) != len(groups):
        raise ValueError(
            "La cantidad de embeddings no coincide "
            "con la cantidad de grupos."
        )

    return [
        cosine_distance(
            embeddings[index],
            embeddings[index + 1],
        )
        for index in range(
            len(embeddings) - 1
        )
    ]


def percentile(
    values: list[float],
    value: float,
) -> float:
    """Calcula un percentil sin dependencias externas."""

    if not values:
        raise ValueError(
            "No existen valores para calcular el percentil."
        )

    if not 0 <= value <= 100:
        raise ValueError(
            "El percentil debe estar entre 0 y 100."
        )

    ordered = sorted(values)

    position = (
        len(ordered) - 1
    ) * value / 100

    lower_index = floor(position)
    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )

    fraction = (
        position - lower_index
    )

    return (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )


def _chunk_text(
    sentences: list[str],
    start: int,
    end: int,
) -> str:
    return " ".join(
        sentences[start : end + 1]
    )


def _split_oversized_range(
    sentences: list[str],
    distances: list[float],
    start: int,
    end: int,
    max_chunk_chars: int,
) -> list[tuple[int, int]]:
    """Divide un rango grande por su mayor cambio semantico."""

    text = _chunk_text(
        sentences,
        start,
        end,
    )

    if len(text) <= max_chunk_chars:
        return [(start, end)]

    if start == end:
        return [(start, end)]

    boundary = max(
        range(start, end),
        key=distances.__getitem__,
    )

    return (
        _split_oversized_range(
            sentences,
            distances,
            start,
            boundary,
            max_chunk_chars,
        )
        + _split_oversized_range(
            sentences,
            distances,
            boundary + 1,
            end,
            max_chunk_chars,
        )
    )


def build_semantic_chunks(
    text: str,
    *,
    breakpoint_percentile: float = 95,
    buffer_size: int = 1,
    max_chunk_chars: int = 3500,
) -> list[str]:
    """Segmenta texto mediante embeddings y breakpoints por percentil."""

    if max_chunk_chars <= 0:
        raise ValueError(
            "max_chunk_chars debe ser mayor que cero."
        )

    sentences = split_into_sentences(
        text,
        max_sentence_chars=max_chunk_chars,
    )

    if not sentences:
        return []

    if len(sentences) == 1:
        return [sentences[0]]

    distances = calculate_semantic_distances(
        sentences,
        buffer_size=buffer_size,
    )

    breakpoints: set[int] = set()

    if (
        len(distances) > 1
        and max(distances) - min(distances) > 1e-9
    ):
        threshold = percentile(
            distances,
            breakpoint_percentile,
        )

        breakpoints = {
            index
            for index, distance in enumerate(
                distances
            )
            if distance > threshold
        }

    ranges: list[tuple[int, int]] = []
    start = 0

    for index in range(
        len(sentences) - 1
    ):
        if index in breakpoints:
            ranges.append(
                (start, index)
            )
            start = index + 1

    ranges.append(
        (
            start,
            len(sentences) - 1,
        )
    )

    final_ranges: list[tuple[int, int]] = []

    for range_start, range_end in ranges:
        final_ranges.extend(
            _split_oversized_range(
                sentences,
                distances,
                range_start,
                range_end,
                max_chunk_chars,
            )
        )

    chunks = [
        _chunk_text(
            sentences,
            start,
            end,
        )
        for start, end in final_ranges
    ]

    if any(
        len(chunk) > max_chunk_chars
        for chunk in chunks
    ):
        raise RuntimeError(
            "La segmentacion genero un chunk "
            "mayor que el limite."
        )

    return chunks
