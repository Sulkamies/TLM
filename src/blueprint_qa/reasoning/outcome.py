"""Internal result types of the Answer Reasoner (private to ``reasoning/``).

``Msg`` is a language-independent description of an explanation; ``explanations.py``
renders it in en/de/fi. ``Stop`` is raised inside the computation when no value can
be given; ``reasoner.answer`` turns it into an ``Answer`` with ``value=None``. It never
leaves this package (R5.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from blueprint_qa.contracts import AnswerStatus, EntityRef


@dataclass(frozen=True)
class Msg:
    """One explanation sentence: a template key plus typed slots."""

    key: str
    what: tuple[EntityRef, ...] = ()
    n: int | None = None
    ordinal: int | None = None
    storey: str | None = None
    measure: str | None = None
    aggregation: str | None = None
    value: float | None = None
    unit: str | None = None
    lhs: float | None = None
    rhs: float | None = None
    rhs_what: tuple[EntityRef, ...] = ()
    operator: str | None = None


class Stop(Exception):
    """No value can be produced; carries the status and the explanation."""

    def __init__(self, status: AnswerStatus, msg: Msg) -> None:
        super().__init__(msg.key)
        self.status = status
        self.msg = msg


def cannot(key: str, **slots: object) -> Stop:
    return Stop(AnswerStatus.CANNOT_ANSWER, Msg(key, **slots))  # type: ignore[arg-type]


def clarify(key: str, **slots: object) -> Stop:
    return Stop(AnswerStatus.NEEDS_CLARIFICATION, Msg(key, **slots))  # type: ignore[arg-type]


@dataclass
class Outcome:
    """A computed answer value (SI units, before any requested-unit conversion)."""

    value: float
    msg: Msg
    evidence: list[str] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    notes: list[Msg] = field(default_factory=list)
