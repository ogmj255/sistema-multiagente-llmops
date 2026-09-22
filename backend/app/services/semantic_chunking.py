import re
from math import floor, sqrt

import pysbd

from app.services.embeddings import generate_embeddings

SENTENCE_SEGMENTER = pysbd.Segmenter(
    language="en",
    clean=False,
)

ROMAN_ENUMERATION_END = re.compile(
    r"(?:^|\s)(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\.$"
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


def _merge_roman_enumeration_breaks(
    sentences: list[str],
) -> list[str]:
    """Repara cortes de pySBD tras numerales romanos de lista."""

    merged: list[str] = []
    index = 0

    while index < len(sentences):
        current = sentences[index]

        while (
            index + 1 < len(sentences)
            and ROMAN_ENUMERATION_END.search(current)
        ):
            index += 1
            current = (
                f"{current} {sentences[index]}"
            )

        merged.append(current)
        index += 1

    return merged


def split_into_sentences(
    text: str,
) -> list[str]:
    """Separa el texto limpio en unidades oracionales."""

    normalized = text.strip()

    if not normalized:
        return []

    raw_sentences = SENTENCE_SEGMENTER.segment(
        normalized
    )

    sentences = [
        " ".join(sentence.split())
        for sentence in raw_sentences
        if sentence.strip()
    ]

    return _merge_roman_enumeration_breaks(
        sentences
    )


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


def build_semantic_chunks(
    text: str,
    *,
    breakpoint_percentile: float = 80,
    buffer_size: int = 1,
) -> list[str]:
    """Segmenta texto mediante embeddings y breakpoints por percentil."""

    sentences = split_into_sentences(
        text
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

    chunks: list[str] = []
    start = 0

    for index in range(
        len(sentences) - 1
    ):
        if index in breakpoints:
            chunks.append(
                _chunk_text(
                    sentences,
                    start,
                    index,
                )
            )
            start = index + 1

    chunks.append(
        _chunk_text(
            sentences,
            start,
            len(sentences) - 1,
        )
    )

    return chunks
