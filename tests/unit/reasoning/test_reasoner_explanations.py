"""Fixed explanation templates: en/de/fi, fallback to English, coverage of all keys/values."""

from __future__ import annotations

import pytest
from reasoning_fakes import analysis, question, ref, room, storey

from blueprint_qa.contracts import (
    VOCABULARIES,
    Answer,
    AnswerStatus,
    Comparison,
    Intent,
    RoomType,
    StoreyLevel,
)
from blueprint_qa.reasoning import answer, explanations
from blueprint_qa.reasoning.explanations import (
    TEMPLATES,
    describe_target,
    format_number,
    pick_language,
    render,
)
from blueprint_qa.reasoning.outcome import Msg

KITCHEN = ref("ROOM", room_type=RoomType.KITCHEN)


def _ok(result: object) -> Answer:
    assert isinstance(result, Answer)
    return result


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("en", "en"),
        ("de", "de"),
        ("fi", "fi"),
        ("de-AT", "de"),
        ("FI_fi", "fi"),
        ("sv", "en"),
        ("", "en"),
    ],
)
def test_pick_language(tag: str, expected: str) -> None:
    assert pick_language(tag) == expected


def test_all_languages_have_the_same_template_keys() -> None:
    keys = set(TEMPLATES["en"])
    for lang in explanations.SUPPORTED_LANGUAGES:
        assert set(TEMPLATES[lang]) == keys, lang


@pytest.mark.parametrize("lang", explanations.SUPPORTED_LANGUAGES)
def test_every_template_renders(lang: str) -> None:
    msg_fields = {
        "what": (KITCHEN,),
        "rhs_what": (ref("WHOLE_PLAN"),),
        "n": 2,
        "ordinal": 3,
        "storey": "GROUND",
        "measure": "AREA",
        "aggregation": "SUM",
        "value": 1.5,
        "unit": "m2",
        "lhs": 1.5,
        "rhs": 2.0,
        "operator": "GT",
    }
    for key in TEMPLATES[lang]:
        text = render(Msg(key, **msg_fields), lang)  # type: ignore[arg-type]
        assert text and "{" not in text, (lang, key)


@pytest.mark.parametrize("lang", explanations.SUPPORTED_LANGUAGES)
def test_every_vocabulary_value_has_a_name(lang: str) -> None:
    for value in VOCABULARIES["RoomType"]:
        assert explanations._ROOM_TYPE[lang][value]
    for value in VOCABULARIES["FixtureType"]:
        assert explanations._FIXTURE_TYPE[lang][value]
    for value in VOCABULARIES["StoreyLevel"]:
        assert explanations._STOREY_LEVEL[lang][value]
    for value in VOCABULARIES["EntityCategory"]:
        assert explanations._CATEGORY[lang][value]


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("en", "Number of matching elements (kitchen): 2."),
        ("de", "Anzahl passender Elemente (Küche): 2."),
        ("fi", "Täsmäävien kohteiden määrä (keittiö): 2."),
        ("sv", "Number of matching elements (kitchen): 2."),
    ],
)
def test_count_explanation_per_language(lang: str, expected: str) -> None:
    plan = analysis(rooms=[room(1, RoomType.KITCHEN), room(2, RoomType.KITCHEN)])
    result = _ok(answer(question(Intent.COUNT, [KITCHEN], language=lang), plan))
    assert result.explanation == expected
    assert result.language == ("en" if lang == "sv" else lang)


def test_cannot_answer_explanations_are_localised() -> None:
    plan = analysis(rooms=[room(1, RoomType.KITCHEN)])
    texts = {}
    for lang in ("en", "de", "fi"):
        result = _ok(answer(question(Intent.LENGTH, [KITCHEN], language=lang), plan))
        assert result.status is AnswerStatus.CANNOT_ANSWER
        assert result.language == lang
        texts[lang] = result.explanation
    assert "scale" in texts["en"]
    assert "Maßstab" in texts["de"]
    assert "mittakaava" in texts["fi"]


def test_measure_explanation_decimal_comma_and_unit() -> None:
    plan = analysis(rooms=[room(1, RoomType.KITCHEN, area=9.25)])
    de = _ok(answer(question(Intent.AREA, [KITCHEN], language="de"), plan))
    assert de.explanation == "Fläche (Küche, Summe): 9,25 m²."
    assert de.value == 9.25
    en = _ok(answer(question(Intent.AREA, [KITCHEN], language="en"), plan))
    assert en.explanation == "Area (kitchen, sum): 9.25 m²."


def test_multi_storey_note_in_all_languages() -> None:
    plan = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[room(1, RoomType.KITCHEN, storey="storey_1")],
    )
    expected = {"en": "all 2 storeys", "de": "alle 2 Geschosse", "fi": "kaikki 2 kerrosta"}
    for lang, fragment in expected.items():
        result = _ok(answer(question(Intent.COUNT, [KITCHEN], language=lang), plan))
        assert fragment in result.explanation


def test_comparison_explanation_fi() -> None:
    plan = analysis(rooms=[room(1, RoomType.KITCHEN, area=12.5)])
    comp = Comparison(measure="AREA", operator="GT", threshold=10.0)
    q = question(Intent.COMPARISON, [KITCHEN], comparison=comp, language="fi")
    result = _ok(answer(q, plan))
    assert result.value == 1.0
    assert result.explanation == "Kyllä: Pinta-ala (keittiö) = 12,5 m², eli suurempi kuin 10 m²."


def test_describe_target_with_all_parts() -> None:
    target = ref("ROOM", room_type=RoomType.BEDROOM, storey="UPPER_1", label="MH 2", ordinal=2)
    assert describe_target(target, "en") == 'bedroom, 1st floor above ground, label "MH 2", no. 2'
    assert describe_target(target, "fi") == 'makuuhuone, 2. kerros, merkintä "MH 2", nro 2'
    assert describe_target(ref("WINDOW"), "de") == "Fenster"


def test_format_number_is_display_only() -> None:
    assert format_number(3.0, "en") == "3"
    assert format_number(2.0 / 3.0, "en") == "0.667"
    assert format_number(2.5, "fi") == "2,5"
