import pytest
from app.services import semantic_chunking
from app.services.semantic_chunking import (
    build_context_groups,
    build_semantic_chunks,
    calculate_semantic_distances,
    cosine_distance,
    percentile,
    split_into_sentences,
)


def test_cosine_distance_equal_vectors() -> None:
    assert cosine_distance(
        [1.0, 0.0],
        [1.0, 0.0],
    ) == pytest.approx(0.0)


def test_cosine_distance_different_vectors() -> None:
    assert cosine_distance(
        [1.0, 0.0],
        [0.0, 1.0],
    ) == pytest.approx(1.0)


def test_cosine_distance_rejects_different_dimensions() -> None:
    with pytest.raises(ValueError):
        cosine_distance(
            [1.0],
            [1.0, 0.0],
        )


def test_split_into_sentences() -> None:
    text = (
        "First sentence. "
        "Second sentence! "
        "Third sentence?"
    )

    assert split_into_sentences(text) == [
        "First sentence.",
        "Second sentence!",
        "Third sentence?",
    ]



def test_roman_enumeration_stays_with_following_text() -> None:
    text = (
        "El usuario acepta: iv. "
        "cancelar las tarifas correspondientes."
    )

    assert split_into_sentences(text) == [
        (
            "El usuario acepta: iv. "
            "cancelar las tarifas correspondientes."
        )
    ]


def test_us_abbreviation_is_not_split() -> None:
    text = (
        "The U.S. Government may impose "
        "additional requirements."
    )

    assert split_into_sentences(text) == [
        (
            "The U.S. Government may impose "
            "additional requirements."
        )
    ]


def test_long_sentence_is_not_split_by_character_limit() -> None:
    text = " ".join(
        ["contractual"] * 300
    )

    sentences = split_into_sentences(
        text
    )

    assert sentences == [text]

def test_build_context_groups() -> None:
    sentences = [
        "First.",
        "Second.",
        "Third.",
    ]

    groups = build_context_groups(
        sentences,
        buffer_size=1,
    )

    assert groups == [
        "First. Second.",
        "First. Second. Third.",
        "Second. Third.",
    ]


def test_calculate_semantic_distances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_embeddings(
        texts: list[str],
    ) -> list[list[float]]:
        assert texts == [
            "First. Second.",
            "First. Second. Third.",
            "Second. Third.",
        ]

        return [
            [1.0, 0.0],
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
            "First.",
            "Second.",
            "Third.",
        ],
        buffer_size=1,
    )

    assert distances == pytest.approx(
        [
            0.0,
            1.0,
        ]
    )


def test_percentile() -> None:
    assert percentile(
        [0.1, 0.2, 0.3],
        50,
    ) == pytest.approx(0.2)

    assert percentile(
        [0.1, 0.2, 0.3],
        95,
    ) == pytest.approx(0.29)


def test_two_sentences_do_not_force_breakpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        lambda sentences, buffer_size=1: [0.9],
    )

    chunks = build_semantic_chunks(
        "First sentence. Second sentence.",
    )

    assert chunks == [
        "First sentence. Second sentence."
    ]


def test_uniform_distances_do_not_create_breakpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        lambda sentences, buffer_size=1: [
            0.5,
            0.5,
            0.5,
        ],
    )

    chunks = build_semantic_chunks(
        "First. Second. Third. Fourth.",
    )

    assert chunks == [
        "First. Second. Third. Fourth."
    ]


def test_percentile_creates_semantic_breakpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        semantic_chunking,
        "calculate_semantic_distances",
        lambda sentences, buffer_size=1: [
            0.1,
            0.9,
            0.2,
        ],
    )

    chunks = build_semantic_chunks(
        "First. Second. Third. Fourth.",
        breakpoint_percentile=95,
    )

    assert chunks == [
        "First. Second.",
        "Third. Fourth.",
    ]



def test_empty_text_returns_no_chunks() -> None:
    assert build_semantic_chunks(
        "   "
    ) == []
