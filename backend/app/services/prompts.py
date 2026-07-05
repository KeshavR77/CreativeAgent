"""Prompt loading/rendering (§10, sub-plan 07 uses these against a real model).

``render_prompt(name, **vars)`` reads ``app/prompts/{name}.md`` and substitutes
each ``{{key}}`` token with ``str(value)``. The mock model ignores prompt content
entirely, but prompts must exist and render so the real path is a drop-in later.

Keyless-first: pure filesystem + string work; no heavy imports at module load.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def render_prompt(name: str, /, **vars: object) -> str:
    """Render ``app/prompts/{name}.md``, replacing ``{{key}}`` with ``str(value)``."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in vars.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text
