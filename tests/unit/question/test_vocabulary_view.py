"""The prompt follows the contract vocabulary (rules Q1, Q3)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from blueprint_qa.contracts import DESCRIPTIONS, VOCABULARIES
from blueprint_qa.question import vocabulary_view
from blueprint_qa.question.providers.llm import PROMPT_VERSION, PROMPTS_DIR, build_prompt
from blueprint_qa.question.vocabulary_view import (
    constrained_text_fields,
    plan_descriptions,
    plan_vocabularies,
    question_fields,
    render_examples,
    render_plan_vocabulary,
    render_synonyms,
)

QUESTION_PKG = Path(__file__).resolve().parents[3] / "src" / "blueprint_qa" / "question"
VOCAB_ENUM_NAMES = ("RoomType", "EntityCategory", "OpeningKind")


def test_q1_no_plan_vocabulary_values_in_question_code() -> None:
    """Rule Q1: values live in contracts, words in synonyms/*.yaml, never in question/*.py."""
    vocab = plan_vocabularies()
    values = sorted({v for vals in vocab.values() for v in vals}, key=len, reverse=True)
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
    assert question_fields() == {
        "RoomType": "room_type",
        "EntityCategory": "category",
        "StoreyLevel": "storey",  # interim, contract change 004
    }


def test_plan_vocabulary_lists_every_value_with_its_meaning() -> None:
    text = render_plan_vocabulary()
    vocab, desc = plan_vocabularies(), plan_descriptions()
    for name in question_fields():
        for value in vocab[name]:
            assert f"- {value}: {desc[name][value]}" in text
    assert "### StoreyLevel (field `targets[].storey`)" in text


def test_interim_storey_levels_are_active_until_the_contract_has_them() -> None:
    assert "GROUND" in constrained_text_fields()["storey"]
    assert set(VOCABULARIES) < set(plan_vocabularies())


def test_lighter_option_contract_values_win_and_are_still_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract change 004, lighter option: StoreyLevel lands in contracts, storey stays str."""
    monkeypatch.setattr(
        vocabulary_view, "VOCABULARIES", {**VOCABULARIES, "StoreyLevel": ("GROUND", "ROOF")}
    )
    monkeypatch.setattr(
        vocabulary_view,
        "DESCRIPTIONS",
        {**DESCRIPTIONS, "StoreyLevel": {"GROUND": "Contract ground.", "ROOF": "Roof."}},
    )
    assert constrained_text_fields() == {"storey": ("GROUND", "ROOF")}
    assert question_fields()["StoreyLevel"] == "storey"
    text = render_plan_vocabulary()
    assert "### StoreyLevel (field `targets[].storey`)" in text
    assert "- GROUND: Contract ground." in text and "- ROOF: Roof." in text
    assert "UPPER_1" not in text  # YAML values ignored once the contract defines them


def test_lighter_option_validation_uses_contract_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    from blueprint_qa.question.llm_output import LlmParse

    monkeypatch.setattr(
        vocabulary_view, "VOCABULARIES", {**VOCABULARIES, "StoreyLevel": ("GROUND", "ROOF")}
    )
    monkeypatch.setattr(
        vocabulary_view,
        "DESCRIPTIONS",
        {**DESCRIPTIONS, "StoreyLevel": {"GROUND": "g", "ROOF": "r"}},
    )
    base = {"language": "en", "intent": "COUNT", "aggregation": "SUM", "confidence": 1.0}
    LlmParse.model_validate({**base, "targets": [{"category": "STOREY", "storey": "ROOF"}]})
    with pytest.raises(ValidationError, match="storey must be null or one of GROUND, ROOF"):
        LlmParse.model_validate({**base, "targets": [{"category": "STOREY", "storey": "ATTIC"}]})


def test_entry_dropped_if_a_contract_types_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict option (not chosen): the schema would enforce the values by itself."""
    monkeypatch.setattr(
        vocabulary_view, "_contract_question_fields", lambda: {"StoreyLevel": "storey"}
    )
    assert vocabulary_view.interim_vocabularies() == {}
    assert constrained_text_fields() == {}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- a\n", "top level must be a mapping"),
        ("X:\n  field: not_a_field\n  values: {A: a}\n", "is not an EntityRef field"),
        ("X:\n  field: storey\n  values: {}\n", "has no values"),
        ("X:\n  field: storey\n", "has no values"),
    ],
)
def test_invalid_interim_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str, message: str
) -> None:
    path = tmp_path / "interim.yaml"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(vocabulary_view, "INTERIM_FILE", path)
    with pytest.raises(ValueError, match=message):
        vocabulary_view.interim_vocabularies()


def test_missing_interim_file_means_no_interim_vocabulary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(vocabulary_view, "INTERIM_FILE", tmp_path / "absent.yaml")
    assert vocabulary_view.interim_vocabularies() == {}


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
