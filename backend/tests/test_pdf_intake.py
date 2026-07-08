"""RFP PDF intake: text extraction, brief distillation, and the upload endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.services import pdf_intake

# The real 4-page Cerebelly RFP committed at the repo root — the canonical fixture.
_RFP = Path(__file__).resolve().parents[2] / "cerebelly-sample-rfp.pdf"


@pytest.fixture
def client(clean_env):
    with TestClient(app) as c:
        yield c


def test_extract_text_rejects_non_pdf(clean_env):
    with pytest.raises(pdf_intake.PdfIntakeError):
        pdf_intake.extract_text(b"this is definitely not a pdf")


def test_extract_text_rejects_empty(clean_env):
    with pytest.raises(pdf_intake.PdfIntakeError):
        pdf_intake.extract_text(b"")


@pytest.mark.skipif(not _RFP.exists(), reason="MockBrief.pdf fixture not present")
def test_extract_text_from_real_rfp(clean_env):
    text = pdf_intake.extract_text(_RFP.read_bytes())
    # pypdf can drop spaces on this PDF's font, so match case- and space-insensitively.
    squashed = text.lower().replace(" ", "")
    assert "cerebelly" in squashed
    assert len(text) > 500


def test_brief_from_rfp_keyless_is_deterministic_and_nonempty(clean_env):
    # Keyless -> the mock model distills a deterministic, valid Brief.
    brief = pdf_intake.brief_from_rfp("Some RFP text about a brand challenge.")
    assert brief.brief.strip()
    # deterministic under the mock (same seed -> same output)
    again = pdf_intake.brief_from_rfp("Some RFP text about a brand challenge.")
    assert brief.brief == again.brief


@pytest.mark.skipif(not _RFP.exists(), reason="MockBrief.pdf fixture not present")
def test_create_project_from_pdf_endpoint(client):
    r = client.post(
        "/api/projects/from-pdf",
        files={"file": ("brief.pdf", _RFP.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["state"] == "intake"
    assert body["id"]
    assert body["brief"]["brief"].strip()  # a distilled brief came back
    # the new project shows up in the registry
    listed = client.get("/api/projects").json()
    assert any(p["id"] == body["id"] for p in listed)


def test_from_pdf_rejects_empty_upload(client):
    r = client.post(
        "/api/projects/from-pdf",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400, r.text


def test_from_pdf_rejects_unreadable_pdf(client):
    r = client.post(
        "/api/projects/from-pdf",
        files={"file": ("junk.pdf", b"%PDF-1.4 not really", "application/pdf")},
    )
    assert r.status_code == 422, r.text
