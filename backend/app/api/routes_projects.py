"""Project lifecycle API (§13, sub-plan 03).

Create -> start -> Gate 1 (approve/reject), plus list/detail projections. All
JSON; failures raise ``HTTPException`` which ``app.main`` renders as the
``{"error": {"code", "message"}}`` envelope.

Handlers ``await`` the spawned run task so the response returns once the run has
settled (reached the gate / END), keeping the immediately-following GET and the
SSE backfill deterministic under the mock.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, ValidationError

from app.models.artifacts import Brief, Strategy
from app.models.events import RunState
from app.models.views import ProjectSummary, ProjectView
from app.services.pdf_intake import PdfIntakeError, brief_from_pdf_bytes

# Reject oversized uploads before reading them into memory (RFPs are a few MB).
_MAX_PDF_BYTES = 15 * 1024 * 1024

router = APIRouter(prefix="/api")


class CreateProjectBody(BaseModel):
    brief: str = Field(min_length=1)
    brand_name: str = ""
    constraints: list[str] = Field(default_factory=list)
    audience: str = ""


class GateBody(BaseModel):
    action: str  # "approve" | "reject"
    edits: dict = Field(default_factory=dict)
    notes: str = ""


def _run_manager(request: Request):
    return request.app.state.run_manager


def _registry(request: Request):
    return request.app.state.registry


def _pending_briefs(request: Request) -> dict:
    return request.app.state.pending_briefs


def _brief_for(request: Request, project_id: str) -> Brief:
    briefs = _pending_briefs(request)
    if project_id not in briefs:
        raise HTTPException(status_code=404, detail="unknown project")
    return briefs[project_id]


def _register_project(request: Request, brief: Brief) -> str:
    """Register a new project from a Brief and return its id."""
    project_id = uuid4().hex
    _pending_briefs(request)[project_id] = brief
    _run_manager(request).create(project_id, brief)
    return project_id


@router.post("/projects", status_code=201)
async def create_project(body: CreateProjectBody, request: Request) -> dict:
    brief = Brief(
        brief=body.brief,
        brand_name=body.brand_name,
        constraints=list(body.constraints),
        audience=body.audience,
    )
    project_id = _register_project(request, brief)
    return {"id": project_id, "state": RunState.intake.value}


@router.post("/projects/from-pdf", status_code=201)
async def create_project_from_pdf(request: Request, file: UploadFile = File(...)) -> dict:
    """The normal entry point: upload a client RFP PDF; the reasoning model reads
    it and distills a Brief, which seeds a new project. Returns the distilled brief
    so the UI can show what was understood before the run starts."""
    if file.content_type not in (None, "application/pdf", "application/octet-stream") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="please upload a PDF file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="the uploaded file is empty")
    if len(data) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF too large (max 15 MB)")
    try:
        brief = brief_from_pdf_bytes(data)
    except PdfIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    project_id = _register_project(request, brief)
    return {
        "id": project_id,
        "state": RunState.intake.value,
        "brief": brief.model_dump(),
    }


@router.get("/projects")
async def list_projects(request: Request) -> list[ProjectSummary]:
    return _registry(request).list()


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request) -> ProjectView:
    view = await _run_manager(request).get_view(project_id)
    if view is None:
        raise HTTPException(status_code=404, detail="unknown project")
    return view


@router.post("/projects/{project_id}/start", status_code=202)
async def start_project(project_id: str, request: Request) -> dict:
    brief = _brief_for(request, project_id)
    task = await _run_manager(request).start(project_id, brief)
    await task
    return {"status": "started"}


@router.post("/projects/{project_id}/cancel")
async def cancel_project(project_id: str, request: Request) -> ProjectView:
    if not await _run_manager(request).cancel(project_id):
        raise HTTPException(status_code=404, detail="unknown project")
    return await get_project(project_id, request)


@router.post("/projects/{project_id}/retry")
async def retry_project(project_id: str, request: Request) -> ProjectView:
    task = await _run_manager(request).retry(project_id)
    if task is None:
        raise HTTPException(status_code=409, detail="project is not in an error state")
    await task
    return await get_project(project_id, request)


@router.post("/projects/{project_id}/clarify")
async def clarify_project(project_id: str, request: Request, body: dict) -> ProjectView:
    answers = list(body.get("answers", []))
    task = await _run_manager(request).resume(project_id, {"answers": answers})
    await task
    return await get_project(project_id, request)


@router.post("/projects/{project_id}/gates/strategy")
async def resolve_strategy_gate(
    project_id: str, body: GateBody, request: Request
) -> ProjectView:
    summary = _registry(request).get(project_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="unknown project")
    if summary.state != RunState.awaiting_strategy_approval.value:
        raise HTTPException(
            status_code=409,
            detail=f"project {project_id} is not awaiting strategy approval",
        )
    if body.action == "approve" and body.edits:
        # Validate inline edits at the boundary: applying them must yield a valid
        # Strategy. Reject with 422 rather than corrupting graph state.
        view = await _run_manager(request).get_view(project_id)
        current = view.strategy if view else None
        if current is not None:
            try:
                Strategy.model_validate({**current.model_dump(), **body.edits})
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"invalid strategy edits: {exc.error_count()} error(s)",
                ) from exc
    task = await _run_manager(request).resume(project_id, body.model_dump())
    await task
    return await get_project(project_id, request)
