import pytest
from app.schemas.contract import ContractSection
from app.services import semantic_chunking
from app.services.semantic_chunking import (
    build_chunk_text,
    build_semantic_chunks,
    build_structural_regions,
    calculate_semantic_distances,
    cosine_distance,
    find_protected_boundaries,
    find_structural_boundaries,
    is_protected_continuation_boundary,
    is_structural_anchor_candidate,
)


def make_section(
    order: int,
    content: str,
    **kwargs: object,
) -> ContractSection:
    return ContractSection(
        order=order,
        content=content,
        html_tag=kwargs.pop("html_tag", "p"),
        source_area=kwargs.pop(
            "source_area",
            "content",
        ),
        **kwargs,
    )


def test_cosine_distance_for_equal_vectors() -> None:
    assert cosine_distance(
        [1.0, 0.0],
        [1.0, 0.0],
    ) == pytest.approx(0.0)


def test_cosine_distance_rejects_different_dimensions() -> None:
    with pytest.raises(ValueError):
        cosine_distance(
            [1.0],
            [1.0, 0.0],
        )


def test_calculate_semantic_distances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_embeddings(
        texts: list[str],
    ) -> list[list[float]]:
        assert texts == [
            "first block",
            "second block",
        ]
        return [
            [1.0, 0.0],
            [0.0, 1.0],
        ]

    monkeypatch.setattr(
        semantic_chunking,
        "generate_embeddings",
        fake_embeddings,
    )

    distances = calculate_semantic_distances(
        [
            "first block",
            "second block",
        ]
    )

    assert distances == pytest.approx(
        [1.0]
    )


def test_protect_digit_continuation() -> None:
    previous = make_section(
        1,
        "The subscriber must be at least",
    )
    current = make_section(
        2,
        "18 years old to use the service.",
    )

    assert is_protected_continuation_boundary(
        previous,
        current,
    )


def test_protect_spanish_connector_continuation() -> None:
    previous = make_section(
        1,
        "Estos terminos y",
    )
    current = make_section(
        2,
        "Condiciones regulan el servicio",
    )

    assert is_protected_continuation_boundary(
        previous,
        current,
    )


def test_protect_english_connector_continuation() -> None:
    previous = make_section(
        1,
        "These Terms and",
    )
    current = make_section(
        2,
        "Conditions govern the service",
    )

    assert is_protected_continuation_boundary(
        previous,
        current,
    )


def test_complete_sentence_is_not_protected() -> None:
    previous = make_section(
        1,
        "The first clause ends here.",
    )
    current = make_section(
        2,
        "The second clause begins here.",
    )

    assert not is_protected_continuation_boundary(
        previous,
        current,
    )


def test_table_rows_are_not_protected() -> None:
    previous = make_section(
        1,
        "PLAN A | 20",
        html_tag="tr",
    )
    current = make_section(
        2,
        "PLAN B | 10",
        html_tag="tr",
    )

    assert not is_protected_continuation_boundary(
        previous,
        current,
    )


def test_find_protected_boundaries() -> None:
    sections = [
        make_section(
            1,
            "The subscriber must be at least",
        ),
        make_section(
            2,
            "18 years old.",
        ),
        make_section(
            3,
            "A new clause starts here.",
        ),
    ]

    assert find_protected_boundaries(
        sections
    ) == {0}


def test_html_heading_is_structural_anchor() -> None:
    section = make_section(
        1,
        "Account conditions",
        html_tag="h2",
    )

    assert is_structural_anchor_candidate(
        section
    )


def test_emphasized_uppercase_is_structural_anchor() -> None:
    section = make_section(
        1,
        "LIMITATION OF LIABILITY",
        is_fully_emphasized=True,
    )

    assert is_structural_anchor_candidate(
        section
    )


def test_emphasized_sentence_is_not_anchor() -> None:
    section = make_section(
        1,
        "The subscription fee is non-refundable",
        is_fully_emphasized=True,
    )

    assert not is_structural_anchor_candidate(
        section
    )


def test_heading_change_creates_boundary() -> None:
    sections = [
        make_section(
            1,
            "First contractual paragraph.",
            heading="Introduction",
            heading_level=2,
        ),
        make_section(
            2,
            "Payment terms apply.",
            heading="Payments",
            heading_level=2,
        ),
    ]

    assert find_structural_boundaries(
        sections
    ) == {0}


def test_numbered_title_creates_boundary() -> None:
    sections = [
        make_section(
            1,
            "General introductory text.",
        ),
        make_section(
            2,
            "2. Service Conditions",
        ),
        make_section(
            3,
            "These conditions govern the service.",
        ),
    ]

    assert find_structural_boundaries(
        sections
    ) == {0}


def test_decimal_clause_is_not_top_level_boundary() -> None:
    sections = [
        make_section(
            1,
            "General conditions.",
        ),
        make_section(
            2,
            "2.1 The customer must provide valid data.",
        ),
    ]

    assert find_structural_boundaries(
        sections
    ) == set()


def test_link_only_numbered_index_is_not_boundary() -> None:
    sections = [
        make_section(
            1,
            "Last updated today.",
        ),
        make_section(
            2,
            "1. Introduction",
            is_link_only=True,
            link_count=1,
        ),
    ]

    assert find_structural_boundaries(
        sections
    ) == set()


def test_protected_boundary_overrides_heading_change() -> None:
    sections = [
        make_section(
            1,
            "These Terms and",
            heading="Terms",
            heading_level=2,
        ),
        make_section(
            2,
            "Conditions govern the service.",
            heading="Conditions",
            heading_level=2,
        ),
    ]

    assert find_structural_boundaries(
        sections
    ) == set()


def test_structural_regions_preserve_all_indexes() -> None:
    sections = [
        make_section(
            1,
            "Introduction text.",
            heading="Introduction",
            heading_level=2,
        ),
        make_section(
            2,
            "More introduction.",
            heading="Introduction",
            heading_level=2,
        ),
        make_section(
            3,
            "Payment text.",
            heading="Payments",
            heading_level=2,
        ),
    ]

    regions = build_structural_regions(
        sections
    )

    flattened = [
        index
        for region in regions
        for index in region
    ]

    assert flattened == [0, 1, 2]


def test_chunk_text_joins_protected_boundary() -> None:
    sections = [
        make_section(
            1,
            "These Terms and",
        ),
        make_section(
            2,
            "Conditions apply.",
        ),
    ]

    text = build_chunk_text(
        sections,
        [0, 1],
        {0},
    )

    assert text == (
        "These Terms and Conditions apply."
    )


def test_chunk_text_keeps_normal_block_break() -> None:
    sections = [
        make_section(
            1,
            "First clause.",
        ),
        make_section(
            2,
            "Second clause.",
        ),
    ]

    text = build_chunk_text(
        sections,
        [0, 1],
    )

    assert text == (
        "First clause.\n\nSecond clause."
    )


def test_small_region_remains_single_chunk() -> None:
    sections = [
        make_section(
            1,
            "First clause.",
        ),
        make_section(
            2,
            "Second clause.",
        ),
    ]

    chunks = build_semantic_chunks(
        sections,
        max_chunk_chars=1000,
    )

    assert chunks == [
        [0, 1],
    ]


def test_large_region_splits_at_largest_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sections = [
        make_section(1, "A" * 10),
        make_section(2, "B" * 10),
        make_section(3, "C" * 10),
        make_section(4, "D" * 10),
    ]

    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        lambda texts: [0.1, 0.9, 0.2],
    )

    chunks = build_semantic_chunks(
        sections,
        max_chunk_chars=25,
    )

    assert chunks == [
        [0, 1],
        [2, 3],
    ]


def test_protected_blocks_are_never_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sections = [
        make_section(
            1,
            "These Terms and",
        ),
        make_section(
            2,
            "Conditions apply to the service.",
        ),
        make_section(
            3,
            "Another topic begins here.",
        ),
    ]

    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        lambda texts: [0.9],
    )

    chunks = build_semantic_chunks(
        sections,
        max_chunk_chars=25,
    )

    assert chunks == [
        [0, 1],
        [2],
    ]


def test_small_chunk_is_merged_with_neighbor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sections = [
        make_section(1, "Tiny"),
        make_section(2, "B" * 20),
        make_section(3, "C" * 20),
    ]

    def fake_distances(
        texts: list[str],
    ) -> list[float]:
        if len(texts) == 3:
            return [0.9, 0.1]

        return [0.5]

    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        fake_distances,
    )

    chunks = build_semantic_chunks(
        sections,
        max_chunk_chars=30,
        min_chunk_chars=10,
    )

    assert chunks == [
        [0, 1],
        [2],
    ]


def test_invalid_chunk_size_is_rejected() -> None:
    sections = [
        make_section(
            1,
            "Contract text.",
        )
    ]

    with pytest.raises(ValueError):
        build_semantic_chunks(
            sections,
            max_chunk_chars=0,
        )
