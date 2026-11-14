"""The only bridge between A2 and ``contracts.vocabulary`` (design rules Q1, Q3, Q4).

Renders the prompt sections from ``VOCABULARIES`` / ``DESCRIPTIONS`` at runtime and
loads the language data in ``synonyms/<lang>.yaml``, rejecting anything that is not a
current vocabulary value. No plan value is spelled out in this module.

Field vocabularies (``interim_vocabulary.yaml``) link a free-text ``EntityRef`` field
to a vocabulary whose values it must take (storey levels, contract change 004, lighter
option chosen by ry: ``EntityRef.storey`` stays ``str``, values are a convention).

* Until the contracts define that vocabulary, the values come from the YAML file.
* Once ``contracts.VOCABULARIES`` defines it, the contract values and descriptions win
  and the YAML ``values`` are ignored (the link stays, so A2 keeps enforcing them).
* If a contract ever types the field with a vocabulary, the entry is dropped: the
  output schema then enforces the values by itself.

So applying contract change 004 needs no code change here.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

import yaml
from pydantic import BaseModel, ConfigDict, Field

from blueprint_qa.contracts import DESCRIPTIONS, VOCABULARIES, EntityRef
from blueprint_qa.question.llm_output import LlmParse

SYNONYMS_DIR = Path(__file__).parent / "synonyms"
INTERIM_FILE = Path(__file__).parent / "interim_vocabulary.yaml"
REQUIRED_LANGUAGES: tuple[str, ...] = ("en", "de", "fi")


class Example(BaseModel):
    """One few-shot example; also a test case (design §3, synonyms YAML format)."""

    model_config = ConfigDict(frozen=True)

    id: str
    question: str
    parse: LlmParse


class Synonyms(BaseModel):
    """Validated content of one ``synonyms/<lang>.yaml``."""

    model_config = ConfigDict(frozen=True)

    language: str
    words: dict[str, dict[str, tuple[str, ...]]]  # vocabulary name -> value -> words
    examples: tuple[Example, ...] = Field(default=())


class InterimVocabulary(BaseModel):
    """One entry of ``interim_vocabulary.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str  # the free-text EntityRef field whose values it fixes
    values: dict[str, str] = Field(default_factory=dict)  # value -> meaning (until in contracts)


# --------------------------------------------------------------------------- vocabulary


@lru_cache(maxsize=4)
def _read_interim(path: Path) -> dict[str, InterimVocabulary]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be a mapping")
    out = {str(name): InterimVocabulary.model_validate(raw) for name, raw in data.items()}
    for name, entry in out.items():
        if entry.field not in EntityRef.model_fields:
            raise ValueError(f"{path.name}: {name}.field {entry.field!r} is not an EntityRef field")
    return out


def interim_vocabularies() -> dict[str, InterimVocabulary]:
    """Active field vocabularies, with values from the contracts when they define them."""
    typed = set(_contract_question_fields().values())
    out: dict[str, InterimVocabulary] = {}
    for name, entry in _read_interim(INTERIM_FILE).items():
        if entry.field in typed:
            continue  # the contract types the field; its schema enforces the values
        if name in VOCABULARIES:
            entry = InterimVocabulary(
                field=entry.field,
                values={v: DESCRIPTIONS[name][v] for v in VOCABULARIES[name]},
            )
        elif not entry.values:
            raise ValueError(
                f"{INTERIM_FILE.name}: {name} has no values and is not in contracts.VOCABULARIES"
            )
        out[name] = entry
    return out


def plan_vocabularies() -> dict[str, tuple[str, ...]]:
    """Contract vocabularies plus active interim ones: name -> values."""
    out = dict(VOCABULARIES)
    out.update({n: tuple(e.values) for n, e in interim_vocabularies().items()})
    return out


def plan_descriptions() -> dict[str, dict[str, str]]:
    """Contract descriptions plus active interim ones: name -> value -> meaning."""
    out = {name: dict(desc) for name, desc in DESCRIPTIONS.items()}
    out.update({n: dict(e.values) for n, e in interim_vocabularies().items()})
    return out


def constrained_text_fields() -> dict[str, tuple[str, ...]]:
    """Free-text ``EntityRef`` fields whose values an interim vocabulary fixes."""
    return {e.field: tuple(e.values) for e in interim_vocabularies().values()}


def _annotation_values(annotation: Any) -> tuple[str, ...]:
    """Allowed string values of a (possibly optional) Enum / Literal annotation."""
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        for arg in get_args(annotation):
            if arg is not type(None):
                return _annotation_values(arg)
        return ()
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return tuple(str(m.value) for m in annotation)
    args = get_args(annotation)
    if args and all(isinstance(a, str) for a in args):
        return tuple(args)
    return ()


def _contract_question_fields() -> dict[str, str]:
    out: dict[str, str] = {}
    for field_name, info in EntityRef.model_fields.items():
        values = _annotation_values(info.annotation)
        for vocab, vocab_values in VOCABULARIES.items():
            if values and values == vocab_values:
                out[vocab] = field_name
    return out


def question_fields() -> dict[str, str]:
    """Vocabulary name -> the ``EntityRef`` field that takes its values (if any)."""
    out = _contract_question_fields()
    out.update({name: e.field for name, e in interim_vocabularies().items()})
    return out


def render_plan_vocabulary() -> str:
    """The ``{{PLAN_VOCABULARY}}`` section: every value with its agreed meaning."""
    fields = question_fields()
    descriptions = plan_descriptions()
    blocks: list[str] = []
    for name, values in plan_vocabularies().items():
        if name not in fields:
            continue  # plan-only vocabulary, not something a question can name
        lines = [f"### {name} (field `targets[].{fields[name]}`)"]
        lines += [f"- {value}: {descriptions[name][value]}" for value in values]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- synonyms


def available_languages() -> tuple[str, ...]:
    """Languages that have a synonyms file, required ones first."""
    found = sorted(p.stem for p in SYNONYMS_DIR.glob("*.yaml"))
    return tuple(lang for lang in REQUIRED_LANGUAGES if lang in found) + tuple(
        lang for lang in found if lang not in REQUIRED_LANGUAGES
    )


def _parse_words(lang: str, raw: dict[str, Any]) -> dict[str, dict[str, tuple[str, ...]]]:
    vocabularies = plan_vocabularies()
    words: dict[str, dict[str, tuple[str, ...]]] = {}
    for vocab, entries in raw.items():
        if vocab not in vocabularies:
            raise ValueError(f"synonyms/{lang}.yaml: unknown vocabulary {vocab!r}")
        if not isinstance(entries, dict):
            raise ValueError(f"synonyms/{lang}.yaml: {vocab} must be a mapping")
        parsed: dict[str, tuple[str, ...]] = {}
        for value, items in entries.items():
            if value not in vocabularies[vocab]:
                raise ValueError(f"synonyms/{lang}.yaml: {value!r} is not a {vocab} value")
            if not isinstance(items, list) or not all(
                isinstance(w, str) and w.strip() for w in items
            ):
                raise ValueError(f"synonyms/{lang}.yaml: {vocab}.{value} must list words")
            parsed[str(value)] = tuple(w.strip() for w in items)
        words[vocab] = parsed
    return words


def _parse_examples(lang: str, raw: list[Any]) -> tuple[Example, ...]:
    examples: list[Example] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "question", "expect"}:
            raise ValueError(f"synonyms/{lang}.yaml: each example needs id, question, expect")
        expect = {"language": lang, "confidence": 1.0, **item["expect"]}
        examples.append(
            Example(
                id=str(item["id"]),
                question=str(item["question"]),
                parse=LlmParse.model_validate(expect),
            )
        )
    return tuple(examples)


@lru_cache(maxsize=16)
def load_synonyms(lang: str) -> Synonyms:
    """Load and validate ``synonyms/<lang>.yaml``. Raises ``ValueError`` on bad data."""
    path = SYNONYMS_DIR / f"{lang}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"synonyms/{lang}.yaml: top level must be a mapping")
    raw_examples = data.pop("examples", []) or []
    if not isinstance(raw_examples, list):
        raise ValueError(f"synonyms/{lang}.yaml: examples must be a list")
    return Synonyms(
        language=lang,
        words=_parse_words(lang, data),
        examples=_parse_examples(lang, raw_examples),
    )


def render_synonyms(langs: Sequence[str]) -> str:
    """The ``{{SYNONYMS}}`` section: words per vocabulary value, per language."""
    loaded = [load_synonyms(lang) for lang in langs]
    lines: list[str] = []
    for vocab, values in plan_vocabularies().items():
        for value in values:
            parts = [
                f"{syn.language}: {', '.join(syn.words[vocab][value])}"
                for syn in loaded
                if value in syn.words.get(vocab, {})
            ]
            if parts:
                lines.append(f"- {vocab}.{value} <- " + " | ".join(parts))
    return "\n".join(lines)


def render_examples(langs: Sequence[str]) -> str:
    """The ``{{EXAMPLES}}`` section: question -> expected JSON, per language."""
    blocks: list[str] = []
    for lang in langs:
        for ex in load_synonyms(lang).examples:
            body = json.dumps(
                ex.parse.model_dump(mode="json", exclude_none=True, exclude={"confidence"}),
                ensure_ascii=False,
                sort_keys=True,
            )
            blocks.append(
                f"Question: {json.dumps(ex.question, ensure_ascii=False)}\nOutput: {body}"
            )
    return "\n\n".join(blocks)
