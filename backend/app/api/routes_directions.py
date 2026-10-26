"""Curation-ops API.

Thin handlers over ``RunManager.resume`` — each turns a request into a curation
op and drives the graph one gate step. Every op requires the project to be
``awaiting_curation`` (409 otherwise) and resumes under the per-project lock.
Read endpoints expose the divergence report and the assembled packages.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.models.artifacts import EDITABLE_FIELDS, Direction
from app.models.events import RunState
from app.models.views import ProjectView

router = APIRouter(prefix="/api")


def _rm(request: Request):
    return request.app.state.run_manager


def _require_curation(request: Request, project_id: str) -> None:
    summary = request.app.state.registry.get(project_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="unknown project")
    if summary.state != RunState.awaiting_curation.value:
        raise HTTPException(status_code=409, detail=f"project {project_id} is not awaiting curation")


async def _apply_op(request: Request, project_id: str, op: dict) -> ProjectView:
    _require_curation(request, project_id)
    task = await _rm(request).resume(project_id, op)
    await task
    return await _rm(request).get_view(project_id)


# --------------------------------------------------------------------------- #
# request bodies                                                               #
# --------------------------------------------------------------------------- #
class AnnotateBody(BaseModel):
    text: str
    author: str = "human"


class EditBody(BaseModel):
    field: str
    value: Any = None


class RegenBody(BaseModel):
    field: str


class ForkBody(BaseModel):
    lens_tweak: str | None = None


class MergeBody(BaseModel):
    direction_ids: list[str] = Field(min_length=2)
    field_choices: dict = Field(default_factory=dict)


class FinalizeBody(BaseModel):
    refine: bool | None = None


# --------------------------------------------------------------------------- #
# single-direction ops                                                         #
# --------------------------------------------------------------------------- #
@router.post("/projects/{project_id}/directions/{direction_id}/promote")
async def promote(project_id: str, direction_id: str, request: Request) -> ProjectView:
    return await _apply_op(request, project_id, {"op": "promote", "direction_id": direction_id})


@router.post("/projects/{project_id}/directions/{direction_id}/kill")
async def kill(project_id: str, direction_id: str, request: Request) -> ProjectView:
    return await _apply_op(request, project_id, {"op": "kill", "direction_id": direction_id})


@router.post("/projects/{project_id}/directions/{direction_id}/annotate")
async def annotate(project_id: str, direction_id: str, body: AnnotateBody, request: Request) -> ProjectView:
    return await _apply_op(
        request, project_id, {"op": "annotate", "direction_id": direction_id, "text": body.text, "author": body.author}
    )


def _apply_path(data: dict, field: str, value: Any) -> dict:
    if "." in field:
        parent, child = field.split(".", 1)
        return {**data, parent: {**data[parent], child: value}}
    return {**data, field: value}


@router.post("/projects/{project_id}/directions/{direction_id}/edit")
async def edit(project_id: str, direction_id: str, body: EditBody, request: Request) -> ProjectView:
    _require_curation(request, project_id)
    if body.field not in EDITABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"{body.field!r} is not an editable field")
    # validate at the boundary: the edit must yield a valid Direction.
    view = await _rm(request).get_view(project_id)
    current = next((d for d in view.directions if d.id == direction_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="unknown direction")
    try:
        Direction.model_validate(_apply_path(current.model_dump(), body.field, body.value))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"invalid edit: {exc.error_count()} error(s)") from exc
    return await _apply_op(
        request, project_id, {"op": "edit", "direction_id": direction_id, "field": body.field, "value": body.value}
    )


@router.post("/projects/{project_id}/directions/{direction_id}/regenerate_field")
async def regenerate_field(project_id: str, direction_id: str, body: RegenBody, request: Request) -> ProjectView:
    if body.field not in EDITABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"{body.field!r} is not an editable field")
    return await _apply_op(
        request, project_id, {"op": "regenerate_field", "direction_id": direction_id, "field": body.field}
    )


@router.post("/projects/{project_id}/directions/{direction_id}/recritique")
async def recritique(project_id: str, direction_id: str, request: Request) -> ProjectView:
    return await _apply_op(request, project_id, {"op": "recritique", "direction_id": direction_id})


@router.post("/projects/{project_id}/directions/{direction_id}/fork")
async def fork(project_id: str, direction_id: str, body: ForkBody, request: Request) -> ProjectView:
    return await _apply_op(
        request, project_id, {"op": "fork", "direction_id": direction_id, "lens_tweak": body.lens_tweak}
    )


# --------------------------------------------------------------------------- #
# multi-direction / lifecycle ops                                              #
# --------------------------------------------------------------------------- #
@router.post("/projects/{project_id}/directions/merge")
async def merge(project_id: str, body: MergeBody, request: Request) -> ProjectView:
    return await _apply_op(
        request,
        project_id,
        {"op": "merge", "direction_ids": body.direction_ids, "field_choices": body.field_choices},
    )


@router.post("/projects/{project_id}/finalize")
async def finalize(project_id: str, body: FinalizeBody, request: Request) -> ProjectView:
    return await _apply_op(request, project_id, {"op": "finalize", "refine": body.refine})


# --------------------------------------------------------------------------- #
# visual regeneration ops — no critique/divergence effect #
# --------------------------------------------------------------------------- #
class SketchRegenBody(BaseModel):
    index: int
    prompt: str | None = None


class MoodboardRegenBody(BaseModel):
    index: int
    kind: str | None = None  # optionally force "generated" <-> "sourced"
    prompt: str | None = None  # ignored for sourced


@router.post("/projects/{project_id}/directions/{direction_id}/regenerate_sketch")
async def regenerate_sketch(project_id: str, direction_id: str, body: SketchRegenBody, request: Request) -> ProjectView:
    return await _apply_op(
        request,
        project_id,
        {"op": "regenerate_sketch", "direction_id": direction_id, "index": body.index, "prompt": body.prompt},
    )


@router.post("/projects/{project_id}/directions/{direction_id}/regenerate_sketches")
async def regenerate_sketches(project_id: str, direction_id: str, request: Request) -> ProjectView:
    return await _apply_op(request, project_id, {"op": "regenerate_sketches", "direction_id": direction_id})


@router.post("/projects/{project_id}/directions/{direction_id}/regenerate_moodboard_item")
async def regenerate_moodboard_item(
    project_id: str, direction_id: str, body: MoodboardRegenBody, request: Request
) -> ProjectView:
    return await _apply_op(
        request,
        project_id,
        {
            "op": "regenerate_moodboard_item",
            "direction_id": direction_id,
            "index": body.index,
            "kind": body.kind,
            "prompt": body.prompt,
        },
    )


# --------------------------------------------------------------------------- #
# reads                                                                        #
# --------------------------------------------------------------------------- #
@router.get("/projects/{project_id}/divergence")
async def get_divergence(project_id: str, request: Request) -> dict:
    view = await _rm(request).get_view(project_id)
    if view is None:
        raise HTTPException(status_code=404, detail="unknown project")
    return view.divergence or {}


@router.get("/projects/{project_id}/packages")
async def get_packages(project_id: str, request: Request):
    view = await _rm(request).get_view(project_id)
    if view is None:
        raise HTTPException(status_code=404, detail="unknown project")
    return view.packages
