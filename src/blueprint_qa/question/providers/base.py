"""The ``QuestionProvider`` adapter interface (AGENTS.md §6 A2, design rule Q6)."""

from __future__ import annotations

from typing import Protocol

from blueprint_qa.contracts import ErrorEnvelope, ParsedQuestion


class QuestionProvider(Protocol):
    """Turns one question into a ``ParsedQuestion``.

    Every implementation returns the same ``ParsedQuestion`` for the same question,
    apart from the ``provider`` field. Implementations may raise; ``interpret`` catches.
    """

    def parse(
        self, request_id: str, question: str, locale_hint: str | None
    ) -> ParsedQuestion | ErrorEnvelope: ...
