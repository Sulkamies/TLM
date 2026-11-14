"""``LlmQuestionProvider``: rendered prompt -> ``common.llm`` -> ``mapping`` (default)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from blueprint_qa.common.llm import LlmClient, Prompt, get_llm_client, load_prompt
from blueprint_qa.contracts import ErrorEnvelope, ParsedQuestion, Stage
from blueprint_qa.question.llm_output import LlmParse
from blueprint_qa.question.mapping import to_parsed_question
from blueprint_qa.question.vocabulary_view import (
    available_languages,
    render_examples,
    render_plan_vocabulary,
    render_synonyms,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PROMPT_NAME = "interpret"
PROMPT_VERSION = 1  # bump together with a new prompts/interpret.v<N>.md (R7.7)
LLM_COMPONENT = "question"


def build_prompt(langs: Sequence[str] | None = None) -> Prompt:
    """Load the versioned template and fill it from the contract vocabulary (rule Q3)."""
    langs = tuple(langs) if langs is not None else available_languages()
    return load_prompt(PROMPTS_DIR, PROMPT_NAME, PROMPT_VERSION).render(
        PLAN_VOCABULARY=render_plan_vocabulary(),
        SYNONYMS=render_synonyms(langs),
        EXAMPLES=render_examples(langs),
    )


class LlmQuestionProvider:
    """Interprets questions with the LLM configured for component ``question``."""

    def __init__(self, client: LlmClient | None = None, prompt: Prompt | None = None) -> None:
        self._client = client or get_llm_client(LLM_COMPONENT)
        self._prompt = prompt or build_prompt()

    @property
    def prompt(self) -> Prompt:
        return self._prompt

    def parse(
        self, request_id: str, question: str, locale_hint: str | None
    ) -> ParsedQuestion | ErrorEnvelope:
        result = self._client.generate_structured(
            request_id=request_id,
            stage=Stage.QUESTION,
            prompt=self._prompt,
            data={"question": question, "locale_hint": locale_hint},
            output_model=LlmParse,
        )
        if isinstance(result, ErrorEnvelope):
            return result
        return to_parsed_question(
            result.parsed, request_id=request_id, question=question, provider=result.provider
        )
