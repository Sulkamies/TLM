"""Re-record the interpreter cassettes against the real Gemini API (R7.12).

Run from the repository root, with GEMINI_API_KEY set:

    BP_LLM_RECORD=1 BP_LLM_CASSETTE_DIR=tests/unit/question/cassettes \
        python tests/unit/question/record_cassettes.py

Records every held-out question (question_cases.py) and every few-shot example
(synonyms/*.yaml). Needed after a prompt version, synonyms or vocabulary change.
Not collected by pytest.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from question_cases import all_questions

from blueprint_qa.contracts import ParsedQuestion
from blueprint_qa.question import interpret
from blueprint_qa.question.vocabulary_view import available_languages, load_synonyms


def main() -> int:
    if os.environ.get("BP_LLM_RECORD") != "1" or not os.environ.get("BP_LLM_CASSETTE_DIR"):
        print("Set BP_LLM_RECORD=1 and BP_LLM_CASSETTE_DIR first.", file=sys.stderr)
        return 2
    questions = all_questions() + [
        ex.question for lang in available_languages() for ex in load_synonyms(lang).examples
    ]
    failures = 0
    for i, question in enumerate(questions):
        result = interpret(f"record-{i}", question, None)
        ok = isinstance(result, ParsedQuestion)
        failures += not ok
        summary = result.intent.value if isinstance(result, ParsedQuestion) else result.code
        print(f"[{'ok' if ok else 'FAIL'}] {summary:<12} {question}")
    print(f"{len(questions) - failures}/{len(questions)} recorded")
    return 1 if failures else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
