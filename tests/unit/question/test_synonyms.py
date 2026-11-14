"""synonyms/<lang>.yaml is validated data covering the whole vocabulary (rule Q4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from blueprint_qa.question import vocabulary_view
from blueprint_qa.question.vocabulary_view import (
    REQUIRED_LANGUAGES,
    available_languages,
    load_synonyms,
    plan_vocabularies,
)


@pytest.mark.parametrize("lang", REQUIRED_LANGUAGES)
def test_every_vocabulary_value_has_words(lang: str) -> None:
    syn = load_synonyms(lang)
    for vocab, values in plan_vocabularies().items():
        missing = [v for v in values if not syn.words.get(vocab, {}).get(v)]
        assert missing == [], f"synonyms/{lang}.yaml: add words for {vocab} {missing}"


@pytest.mark.parametrize("lang", REQUIRED_LANGUAGES)
def test_every_language_has_examples(lang: str) -> None:
    syn = load_synonyms(lang)
    assert len(syn.examples) >= 3
    assert all(ex.parse.language == lang for ex in syn.examples)
    assert len({ex.id for ex in syn.examples}) == len(syn.examples)


@pytest.mark.parametrize(
    ("lang", "vocab", "value", "words"),
    [
        ("fi", "RoomType", "BEDROOM", ["MH"]),
        ("fi", "RoomType", "BATHROOM", ["KH", "PH", "KPH"]),
        ("fi", "RoomType", "TOILET", ["WC"]),
        ("fi", "RoomType", "KITCHEN", ["K", "KK"]),
        ("fi", "RoomType", "LIVING_ROOM", ["OH"]),
        ("fi", "RoomType", "SAUNA", ["S"]),
        ("fi", "RoomType", "BALCONY", ["PARVEKE"]),
        ("de", "RoomType", "BEDROOM", ["SZ"]),
        ("de", "RoomType", "LIVING_ROOM", ["WZ"]),
        ("de", "RoomType", "BATHROOM", ["Bad"]),
        ("de", "RoomType", "TOILET", ["Gäste-WC"]),
    ],
)
def test_required_plan_abbreviations(lang: str, vocab: str, value: str, words: list[str]) -> None:
    assert set(words) <= set(load_synonyms(lang).words[vocab][value])


def test_required_languages_come_first() -> None:
    assert available_languages()[:3] == REQUIRED_LANGUAGES


def _with_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    (tmp_path / "xx.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(vocabulary_view, "SYNONYMS_DIR", tmp_path)
    load_synonyms.cache_clear()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("NotAVocab: {}\n", "unknown vocabulary"),
        ("RoomType: {WINE_CELLAR: [x]}\n", "is not a RoomType value"),
        ("RoomType: [x]\n", "must be a mapping"),
        ("RoomType: {SAUNA: x}\n", "must list words"),
        ("RoomType: {SAUNA: ['']}\n", "must list words"),
        ("- a\n", "top level must be a mapping"),
        ("examples: {a: 1}\n", "examples must be a list"),
        ("examples: [{question: q}]\n", "needs id, question, expect"),
    ],
)
def test_invalid_synonyms_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str, message: str
) -> None:
    _with_yaml(monkeypatch, tmp_path, text)
    with pytest.raises(ValueError, match=message):
        load_synonyms("xx")


def test_invalid_example_expectation_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _with_yaml(
        monkeypatch,
        tmp_path,
        "examples:\n  - id: a\n    question: q\n    expect: {intent: COUNT, aggregation: SUM,"
        " targets: [{category: NOT_A_CATEGORY}]}\n",
    )
    with pytest.raises(ValueError):
        load_synonyms("xx")


def test_empty_file_and_extra_languages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _with_yaml(monkeypatch, tmp_path, "")
    assert load_synonyms("xx").words == {}
    assert available_languages() == ("xx",)
