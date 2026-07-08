"""RFP PDF intake — the normal entry point: drop a client's RFP PDF, get a Brief.

``extract_text`` pulls the raw text out of the PDF; ``brief_from_rfp`` hands that
text to the reasoning model (real or mock) to distill a structured
:class:`~app.models.artifacts.Brief`. Keyless-first: with no provider key the mock
model produces a deterministic brief, so the endpoint and its tests run offline.
"""

from __future__ import annotations

import io
import logging

from pydantic import BaseModel, Field, field_validator
from pypdf import PdfReader

from app.models.artifacts import Brief
from app.services.models import generate_structured, get_chat_model
from app.services.prompts import render_prompt

logger = logging.getLogger("app.pdf_intake")


class _RfpDraft(BaseModel):
    """Lenient intake schema. A model reading a messy RFP may return a field as a
    list of sentences where we want a string (or a bare string where we want a
    list) — coerce both directions rather than 500 on a shape mismatch."""

    brief: str = ""
    brand_name: str = ""
    audience: str = ""
    constraints: list[str] = Field(default_factory=list)

    @field_validator("brief", "brand_name", "audience", mode="before")
    @classmethod
    def _to_text(cls, v: object) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return " ".join(str(x).strip() for x in v if str(x).strip())
        return str(v)

    @field_validator("constraints", mode="before")
    @classmethod
    def _to_list(cls, v: object) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [v]
        return [str(x).strip() for x in v if str(x).strip()]

# Cap the text handed to the model — RFPs are a few pages; this bounds tokens and
# leaves headroom under any context limit while keeping the whole brief in view.
_MAX_CHARS = 24_000


class PdfIntakeError(Exception):
    """The uploaded file could not be turned into a usable brief."""


def extract_text(data: bytes) -> str:
    """Extract all text from a PDF byte string. Raises PdfIntakeError if the file
    is not a readable PDF or carries no extractable text (e.g. a scanned image)."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf raises a variety of types
        raise PdfIntakeError(f"could not read the PDF: {exc}") from exc
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - one bad page must not sink the upload
            continue
    text = "\n".join(parts).strip()
    if not text:
        raise PdfIntakeError(
            "no extractable text in the PDF (it may be a scanned image — "
            "upload a text-based PDF or paste the brief directly)"
        )
    return text


def brief_from_rfp(text: str, *, project_id: str = "") -> Brief:
    """Distill extracted RFP text into a structured Brief via the reasoning model.

    Distills into the lenient ``_RfpDraft`` (tolerant of list/string shape drift
    from the model) and maps to the canonical ``Brief``."""
    model = get_chat_model("rfp_intake", project_id=project_id, temperature=0.2)
    prompt = render_prompt("rfp_intake", rfp=text[:_MAX_CHARS])
    draft = generate_structured(model, prompt, _RfpDraft)
    if not draft.brief.strip():
        raise PdfIntakeError("could not distill a brief from the RFP text")
    brief = Brief(
        brief=draft.brief.strip(),
        brand_name=draft.brand_name.strip(),
        audience=draft.audience.strip(),
        constraints=draft.constraints,
    )
    logger.info("distilled RFP into brief: %s", brief.brief[:120])
    return brief


def brief_from_pdf_bytes(data: bytes, *, project_id: str = "") -> Brief:
    """Convenience: PDF bytes -> Brief (extract then distill)."""
    return brief_from_rfp(extract_text(data), project_id=project_id)
