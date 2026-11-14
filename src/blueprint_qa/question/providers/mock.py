"""``MockQuestionProvider``: canned answers for tests (R7.3). No network, no LLM."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from blueprint_qa.contracts import ErrorEnvelope, ParsedQuestion, Stage
from blueprint_qa.question.llm_output import LlmParse
from blueprint_qa.question.mapping import to_parsed_question
from blueprint_qa.question.vocabulary_view import available_languages, load_synonyms

MOCK_PROVIDER = "mock"


class MockQuestionProvider:
    """Returns a canned interpretation for each known question.

    Canned entries are ``LlmParse`` objects, so they pass through the same
    ``mapping`` as the LLM provider and give identical ``ParsedQuestion``s (rule Q6).
    Unknown questions give ``QUESTION_PARSE_FAILED``.
    """

    def __init__(self, canned: Mapping[str, LlmParse]) -> None:
        self._canned = {self._key(q): p for q, p in canned.items()}

    @staticmethod
    def _key(question: str) -> str:
        return " ".join(question.split()).casefold()

    @classmethod
    def from_examples(cls, langs: Sequence[str] | None = None) -> MockQuestionProvider:
        """Canned answers from the few-shot examples in ``synonyms/<lang>.yaml``."""
        langs = tuple(langs) if langs is not None else available_languages()
        return cls({ex.question: ex.parse for lang in langs for ex in load_synonyms(lang).examples})

    def parse(
        self, request_id: str, question: str, locale_hint: str | None
    ) -> ParsedQuestion | ErrorEnvelope:
        canned = self._canned.get(self._key(question))
        if canned is None:
            return ErrorEnvelope(
                request_id=request_id,
                stage=Stage.QUESTION,
                code="QUESTION_PARSE_FAILED",
                message="The question could not be interpreted.",
                retryable=False,
                details={"provider": MOCK_PROVIDER, "detail": "no canned answer"},
            )
        return to_parsed_question(
            canned, request_id=request_id, question=question, provider=MOCK_PROVIDER
        )
