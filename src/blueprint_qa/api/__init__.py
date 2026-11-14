"""A0 front door (AGENTS.md §2.1): the command-line interface.

Run ``python -m blueprint_qa.api <file> "<question>"``. It only calls the orchestrator.
"""

from blueprint_qa.api.cli import main

__all__ = ["main"]
