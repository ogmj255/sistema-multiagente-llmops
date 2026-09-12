import re
from math import sqrt

from app.schemas.contract import ContractSection
from app.services.embeddings import generate_embeddings

CONTINUATION_CONNECTORS = frozenset(
    {
        "y",
        "e",
        "o",
        "u",
        "ni",
        "and",
        "or",
        "nor",
    }
)

LEADING_CONTINUATION_CHARS = frozenset(
    {
        '"',
        "'",
        "(",
        "[",
        "{",
        "\u201c",
        "\u201d",
        "\u2018",
        "\u2019",
    }
)

NON_CONTINUABLE_TAGS = frozenset({"li", "tr"})

TERMINAL_BOUNDARY_PUNCTUATION = (
    ".",
    "!",
    "?",
    ";",
    ":",
)

STRUCTURAL_ANCHOR_MAX_WORDS = 14
STRUCTURAL_ANCHOR_MAX_CHARS = 160

STRUCTURAL_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

TOP_LEVEL_NUMBERED_HEADING_PATTERN = re.compile(r"^\d+\.\s+\S")


def is_protected_continuation_boundary(
    previous_section: ContractSection,
    current_section: ContractSection,
) -> bool:
    """Detecta una frontera HTML que pertenece al mismo texto."""

    if previous_section.source_area != current_section.source_area:
        return False

    if previous_section.html_tag != current_section.html_tag:
        return False

    if previous_section.html_tag in NON_CONTINUABLE_TAGS:
        return False

    if previous_section.is_fully_emphasized or current_section.is_fully_emphasized:
        return False

    previous_content = previous_section.content.strip()
    current_content = current_section.content.strip()

    if not previous_content or not current_content:
        return False

    if previous_content.endswith(TERMINAL_BOUNDARY_PUNCTUATION):
        return False

    continuation = current_content.lstrip()

    while continuation and continuation[0] in LEADING_CONTINUATION_CHARS:
        continuation = continuation[1:].lstrip()

    if not continuation:
        return False

    if continuation[0].islower() or continuation[0].isdigit():
        return True

    last_token = previous_content.rsplit(maxsplit=1)[-1].casefold()

    last_word = "".join(character for character in last_token if character.isalpha())

    return last_word in CONTINUATION_CONNECTORS


def find_protected_boundaries(
    sections: list[ContractSection],
) -> set[int]:
    """Devuelve fronteras que nunca deben convertirse en cortes."""

    protected: set[int] = set()

    for index in range(len(sections) - 1):
        if is_protected_continuation_boundary(
            sections[index],
            sections[index + 1],
        ):
            protected.add(index)

    return protected


def is_structural_anchor_candidate(
    section: ContractSection,
) -> bool:
    """Detecta una señal visual clara de encabezado."""

    content = section.content.strip()

    if (
        not content
        or section.is_link_only
        or section.html_tag in NON_CONTINUABLE_TAGS
        or len(content) > STRUCTURAL_ANCHOR_MAX_CHARS
        or len(content.split()) > STRUCTURAL_ANCHOR_MAX_WORDS
    ):
        return False

    if section.html_tag in STRUCTURAL_HEADING_TAGS:
        return True

    if not section.is_fully_emphasized:
        return False

    return content.isupper() or content.endswith(":") or len(content.split()) <= 4


def _is_top_level_numbered_heading(
    section: ContractSection,
) -> bool:
    """Detecta un título numerado de primer nivel."""

    content = section.content.strip()

    if (
        not content
        or section.is_link_only
        or section.html_tag in NON_CONTINUABLE_TAGS
        or len(content) > STRUCTURAL_ANCHOR_MAX_CHARS
        or len(content.split()) > STRUCTURAL_ANCHOR_MAX_WORDS
    ):
        return False

    if content.endswith((".", "!", "?", ";")):
        return False

    return bool(TOP_LEVEL_NUMBERED_HEADING_PATTERN.match(content))


def _normalized_heading(
    section: ContractSection,
) -> str | None:
    if section.heading is None:
        return None

    heading = section.heading.strip()

    return heading or None


def find_structural_boundaries(
    sections: list[ContractSection],
) -> set[int]:
    """Detecta fronteras estructurales confiables."""

    if len(sections) < 2:
        return set()

    protected = find_protected_boundaries(sections)

    boundaries: set[int] = set()

    for index in range(len(sections) - 1):
        if index in protected:
            continue

        previous = sections[index]
        current = sections[index + 1]

        previous_heading = _normalized_heading(previous)
        current_heading = _normalized_heading(current)

        heading_changed = current_heading is not None and (
            current_heading != previous_heading
            or (current.heading_level != previous.heading_level)
        )

        previous_marker = is_structural_anchor_candidate(
            previous
        ) or _is_top_level_numbered_heading(previous)

        current_marker = is_structural_anchor_candidate(
            current
        ) or _is_top_level_numbered_heading(current)

        marker_started = current_marker and not previous_marker

        if heading_changed or marker_started:
            boundaries.add(index)

    return boundaries


def build_structural_regions(
    sections: list[ContractSection],
) -> list[list[int]]:
    """Construye regiones antes de aplicar la división semántica."""

    if not sections:
        return []

    boundaries = find_structural_boundaries(sections)

    regions: list[list[int]] = []
    start = 0

    for boundary in sorted(boundaries):
        regions.append(list(range(start, boundary + 1)))
        start = boundary + 1

    regions.append(list(range(start, len(sections))))

    return regions


def cosine_distance(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """Calcula distancia coseno entre dos vectores."""

    if not vector_a or not vector_b:
        raise ValueError("Los vectores no pueden estar vacíos.")

    if len(vector_a) != len(vector_b):
        raise ValueError("Los vectores deben tener la misma dimensión.")

    dot_product = sum(
        value_a * value_b
        for value_a, value_b in zip(
            vector_a,
            vector_b,
            strict=True,
        )
    )

    norm_a = sqrt(sum(value * value for value in vector_a))
    norm_b = sqrt(sum(value * value for value in vector_b))

    if norm_a == 0 or norm_b == 0:
        raise ValueError("No se puede usar un vector nulo.")

    similarity = dot_product / (norm_a * norm_b)

    return 1.0 - similarity


def calculate_semantic_distances(
    texts: list[str],
) -> list[float]:
    """Calcula distancia semántica entre bloques adyacentes."""

    if len(texts) < 2:
        return []

    normalized = [text.strip() for text in texts]

    if any(not text for text in normalized):
        raise ValueError("Los bloques semánticos no pueden estar vacíos.")

    embeddings = generate_embeddings(normalized)

    if len(embeddings) != len(normalized):
        raise ValueError(
            "La cantidad de embeddings no coincide con la cantidad de bloques."
        )

    return [
        cosine_distance(
            embeddings[index],
            embeddings[index + 1],
        )
        for index in range(len(embeddings) - 1)
    ]


def build_chunk_text(
    sections: list[ContractSection],
    indexes: list[int],
    protected_boundaries: set[int] | None = None,
) -> str:
    """Construye el texto final de un chunk."""

    if not indexes:
        raise ValueError("El chunk debe contener al menos un bloque.")

    protected = protected_boundaries if protected_boundaries is not None else set()

    parts: list[str] = []

    for position, index in enumerate(indexes):
        if index < 0 or index >= len(sections):
            raise ValueError("Existe un índice fuera del rango.")

        content = sections[index].content.strip()

        if not content:
            raise ValueError("Un bloque del chunk esta vacio.")

        if position == 0:
            parts.append(content)
            continue

        previous_index = indexes[position - 1]

        if index != previous_index + 1:
            raise ValueError("Los bloques del chunk deben ser contiguos.")

        separator = " " if previous_index in protected else "\n\n"

        parts.append(separator + content)

    return "".join(parts)


def _group_text(
    sections: list[ContractSection],
    indexes: list[int],
) -> str:
    return " ".join(sections[index].content.strip() for index in indexes)


def _build_atomic_groups(
    indexes: list[int],
    protected_boundaries: set[int],
) -> list[list[int]]:
    if not indexes:
        return []

    groups: list[list[int]] = []
    current = [indexes[0]]

    for index in indexes[1:]:
        previous_index = current[-1]

        if previous_index in protected_boundaries and index == previous_index + 1:
            current.append(index)
            continue

        groups.append(current)
        current = [index]

    groups.append(current)

    return groups


def _flatten_groups(
    groups: list[list[int]],
) -> list[int]:
    return [index for group in groups for index in group]


def _split_atoms_recursively(
    sections: list[ContractSection],
    atoms: list[list[int]],
    max_chunk_chars: int,
) -> list[list[int]]:
    indexes = _flatten_groups(atoms)

    if len(_group_text(sections, indexes)) <= max_chunk_chars or len(atoms) <= 1:
        return [indexes]

    texts = [
        _group_text(
            sections,
            atom,
        )
        for atom in atoms
    ]

    distances = calculate_semantic_distances(texts)

    if len(distances) != len(atoms) - 1:
        raise ValueError("Cantidad inesperada de distancias semánticas.")

    best_boundary = max(
        range(len(distances)),
        key=distances.__getitem__,
    )

    left = atoms[: best_boundary + 1]
    right = atoms[best_boundary + 1 :]

    return _split_atoms_recursively(
        sections,
        left,
        max_chunk_chars,
    ) + _split_atoms_recursively(
        sections,
        right,
        max_chunk_chars,
    )


def _merge_small_chunks(
    sections: list[ContractSection],
    chunks: list[list[int]],
    min_chunk_chars: int,
) -> list[list[int]]:
    if min_chunk_chars == 0 or len(chunks) <= 1:
        return chunks

    merged: list[list[int]] = []

    for chunk in chunks:
        chunk_size = len(
            _group_text(
                sections,
                chunk,
            )
        )

        if merged and chunk_size < min_chunk_chars:
            merged[-1].extend(chunk)
        else:
            merged.append(list(chunk))

    if (
        len(merged) > 1
        and len(
            _group_text(
                sections,
                merged[0],
            )
        )
        < min_chunk_chars
    ):
        merged[1] = merged[0] + merged[1]
        merged = merged[1:]

    return merged


def build_semantic_chunks(
    sections: list[ContractSection],
    *,
    max_chunk_chars: int,
    min_chunk_chars: int = 0,
) -> list[list[int]]:
    """Construye chunks usando estructura y cambio semántico."""

    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars debe ser mayor que cero.")

    if min_chunk_chars < 0:
        raise ValueError("min_chunk_chars no puede ser negativo.")

    if min_chunk_chars > max_chunk_chars:
        raise ValueError("min_chunk_chars no puede superar max_chunk_chars.")

    if not sections:
        return []

    protected = find_protected_boundaries(sections)

    regions = build_structural_regions(sections)

    chunks: list[list[int]] = []

    for region in regions:
        atoms = _build_atomic_groups(
            region,
            protected,
        )

        region_chunks = _split_atoms_recursively(
            sections,
            atoms,
            max_chunk_chars,
        )

        region_chunks = _merge_small_chunks(
            sections,
            region_chunks,
            min_chunk_chars,
        )

        chunks.extend(region_chunks)

    flattened = [index for chunk in chunks for index in chunk]

    if flattened != list(range(len(sections))):
        raise RuntimeError("La segmentación perdió o duplicó bloques.")

    return chunks
