"""The prompt follows the contract vocabulary (rules Q1, Q3)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from blueprint_qa.contracts import DESCRIPTIONS, VOCABULARIES
from blueprint_qa.question import vocabulary_view
from blueprint_qa.question.providers.llm import PROMPT_VERSION, PROMPTS_DIR, build_prompt
from blueprint_qa.question.vocabulary_view import (
    question_fields,
    render_examples,
    render_plan_vocabulary,
    render_synonyms,
)

QUESTION_PKG = Path(__file__).resolve().parents[3] / "src" / "blueprint_qa" / "question"
VOCAB_ENUM_NAMES = ("RoomType", "EntityCategory", "OpeningKind")


def test_q1_no_plan_vocabulary_values_in_question_code() -> None:
    """Rule Q1: values live in contracts, words in synonyms/*.yaml, never in question/*.py."""
    values = sorted({v for vals in VOCABULARIES.values() for v in vals}, key=len, reverse=True)
    quoted = re.compile(r"""["'](""" + "|".join(map(re.escape, values)) + r""")["']""")
    member = re.compile(r"\b(" + "|".join(VOCAB_ENUM_NAMES) + r")\.[A-Z_]+\b")
    offenders = []
    for path in QUESTION_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in (quoted, member):
            offenders += [f"{path.name}: {m.group(0)}" for m in pattern.finditer(text)]
    assert offenders == []


def test_q1_guard_detects_violations() -> None:
    values = "|".join(VOCABULARIES["RoomType"])
    assert re.search(r"""["'](""" + values + r""")["']""", 'if t == "SAUNA":')
    assert re.search(r"\b(RoomType)\.[A-Z_]+\b", "x = RoomType.BEDROOM")


def test_question_fields_found_from_entity_ref() -> None:
    assert question_fields() == {"RoomType": "room_type", "EntityCategory": "category"}


def test_plan_vocabulary_lists_every_value_with_its_meaning() -> None:
    text = render_plan_vocabulary()
    for name in question_fields():
        for value in VOCABULARIES[name]:
            assert f"- {value}: {DESCRIPTIONS[name][value]}" in text


def test_prompt_follows_a_vocabulary_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a value in contracts reaches the prompt with no A2 code change."""
    vocab = {**VOCABULARIES, "RoomType": (*VOCABULARIES["RoomType"], "WINE_CELLAR")}
    desc = {**DESCRIPTIONS, "RoomType": {**DESCRIPTIONS["RoomType"], "WINE_CELLAR": "Wine room."}}
    monkeypatch.setattr(vocabulary_view, "VOCABULARIES", vocab)
    monkeypatch.setattr(vocabulary_view, "DESCRIPTIONS", desc)
    # A real contract change also extends EntityRef.room_type; simulate that link here.
    monkeypatch.setattr(vocabulary_view, "question_fields", lambda: {"RoomType": "room_type"})
    assert "- WINE_CELLAR: Wine room." in render_plan_vocabulary()


def test_synonyms_and_examples_rendered_for_all_languages() -> None:
    syn = render_synonyms(["en", "de", "fi"])
    assert "makuuhuone" in syn and "Schlafzimmer" in syn and "bedroom" in syn
    ex = render_examples(["en", "de", "fi"])
    assert "Onko asunnossa erillistä vessaa?" in ex
    assert '"confidence"' not in ex


def test_prompt_template_has_only_the_designed_placeholders() -> None:
    from blueprint_qa.common.llm import load_prompt

    tpl = load_prompt(PROMPTS_DIR, "interpret", PROMPT_VERSION)
    assert tpl.placeholders == {"PLAN_VOCABULARY", "SYNONYMS", "EXAMPLES"}
    rendered = build_prompt()
    assert rendered.ref == f"interpret@v{PROMPT_VERSION}"
    assert "{{" not in rendered.text
