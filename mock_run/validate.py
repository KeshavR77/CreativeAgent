"""Validate the mock_run/ document set against the live data contracts.

Run from the repo root:

    backend/.venv/bin/python mock_run/validate.py

Checks that every mock agent-output document still parses under the real
Pydantic models (app/models/artifacts.py), that critic verdicts match the
code-computed rule, that visual provenance and hybrid-moodboard invariants
hold, that the mock human feedback uses the exact gate resume-payload shapes,
and that the deliverables are byte-identical to what the repo's deterministic
renderers produce from the mock package. Exits 0/1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.api.routes_export import render_export_markdown  # noqa: E402
from app.models.artifacts import (  # noqa: E402
    EDITABLE_FIELDS,
    Brief,
    ConceptPackage,
    CostRecord,
    CreativeBrief,
    CritiqueScore,
    Direction,
    ResearchDossier,
    Strategy,
    Territory,
    VerbalIdentity,
)
from app.services.tokens import build_tokens_css, build_tokens_json  # noqa: E402

MOCK = ROOT / "mock_run"
AGENT = MOCK / "agent_outputs"
HUMAN = MOCK / "human_feedback"
DELIV = MOCK / "deliverables"

# Every curation op the gate understands (app/graph/curation.py::curation_gate).
KNOWN_OPS = {
    "promote", "kill", "annotate", "edit", "regenerate_field", "recritique",
    "fork", "merge", "regenerate_sketch", "regenerate_sketches",
    "regenerate_moodboard_item", "finalize",
}

errors: list[str] = []
checked = 0


def check(label: str, fn) -> None:
    global checked
    checked += 1
    try:
        fn()
        print(f"  ok  {label}")
    except Exception as exc:  # noqa: BLE001 - report every failure, then exit 1
        errors.append(f"{label}: {exc}")
        print(f"FAIL  {label}: {exc}")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def expect_verdict(c: CritiqueScore) -> None:
    # mirrors app/graph/exploration.py::compute_verdict — verdict is computed
    # in code, never taken from the model.
    avg = (c.distinctiveness + c.strategic_fit + c.memorability
           + c.audience_resonance + c.feasibility) / 5.0
    expected = "ship" if avg >= 4.0 else ("revise" if avg >= 2.5 else "kill")
    assert c.verdict == expected, f"verdict {c.verdict!r} != computed {expected!r} (avg {avg})"


def check_direction(path: Path) -> Direction:
    d = Direction.model_validate(load(path))
    assert len(d.sketches) == 3, f"expected SKETCH_COUNT=3 sketches, got {len(d.sketches)}"
    assert all(s.kind == "generated" for s in d.sketches), "sketches must all be generated"
    assert len({s.gen_prompt for s in d.sketches}) == 3, "sketch gen_prompts must be distinct"
    board = d.art_direction.moodboard
    assert len(board) == 9, f"expected MOODBOARD_SIZE=9 tiles, got {len(board)}"
    kinds = {t.kind for t in board}
    assert {"generated", "sourced"} <= kinds, f"moodboard must be hybrid, got kinds {kinds}"
    if d.critique is not None:
        expect_verdict(d.critique)
    return d


def main() -> int:
    # --- agent outputs ----------------------------------------------------
    check("00_input_brief", lambda: Brief.model_validate(load(MOCK / "00_input_brief.json")))
    check("01_research_dossier", lambda: ResearchDossier.model_validate(load(AGENT / "01_research_dossier.json")))
    check("02_strategy_v1", lambda: Strategy.model_validate(load(AGENT / "02_strategy_v1.json")))
    check("03_strategy_v2", lambda: Strategy.model_validate(load(AGENT / "03_strategy_v2.json")))
    check("04_verbal_identity", lambda: VerbalIdentity.model_validate(load(AGENT / "04_verbal_identity.json")))
    check("05_creative_brief", lambda: CreativeBrief.model_validate(load(AGENT / "05_creative_brief.json")))

    def territories():
        ts = [Territory.model_validate(t) for t in load(AGENT / "06_territories.json")["territories"]]
        assert len(ts) == 3 and len({t.label for t in ts}) == 3
    check("06_territories", territories)

    directions: dict[str, Direction] = {}

    def add_direction(name: str):
        d = check_direction(AGENT / name)
        directions[d.id] = d
    for name in (
        "07a_direction_the_receipt.json",
        "07b_direction_built_to_rebuild.json",
        "07c_direction_anti_hype.json",
        "09_direction_the_receipt_v2.json",
        "10_direction_fork_receipt_box.json",
        "11_direction_merged_living_receipt.json",
    ):
        check(name.removesuffix(".json"), lambda n=name: add_direction(n))

    def divergence_initial():
        rep = load(AGENT / "08_divergence_initial.json")
        assert set(rep) == {"min", "mean", "warning", "scores"}
        assert rep["min"] <= rep["mean"] and rep["warning"] is False
        assert len(rep["scores"]) == 3
    check("08_divergence_initial", divergence_initial)

    def divergence_final():
        rep = load(AGENT / "12_divergence_final.json")
        # <2 active directions after the merge: divergence is undefined (nulls).
        assert rep == {"min": None, "mean": None, "warning": False}
    check("12_divergence_final", divergence_final)

    def lineage():
        fork = directions["dir-9e61b47d20"]
        merged = directions["dir-5a2f8c03e7"]
        assert fork.parent_id == "dir-4c9e2a71b3" and fork.lens_tweak
        assert merged.merged_from == ["dir-4c9e2a71b3", "dir-8d17f0a2c5"]
        assert merged.status == "promoted" and merged.divergence_score is None
    check("lineage (fork parent_id / merge merged_from)", lineage)

    def curation_summary():
        doc = load(AGENT / "13_curation_summary_final.json")
        assert doc["gate"] == "curation"
        rows = {r["id"]: r for r in doc["directions"]}
        assert len(rows) == 5
        statuses = {r["status"] for r in rows.values()}
        assert statuses == {"merged_away", "killed", "promoted"}
        for row in rows.values():
            if row["critique"]:
                expect_verdict(CritiqueScore.model_validate(row["critique"]))
        # regenerate_field marked Anti-Hype stale and it was never recritiqued.
        assert rows["dir-b3e94d10fa"]["critique_stale"] is True
    check("13_curation_summary_final", curation_summary)

    package = ConceptPackage.model_validate(load(AGENT / "14_concept_package.json"))

    def package_checks():
        assert package.strategy.key_message == "Don't take our word for it. Read the receipt."
        assert package.rationale.endswith(package.strategy.key_message)
        assert all(s.kind == "generated" for s in package.sketches)
        assert package.names, "package must carry the (unscreened) candidate names"
    check("14_concept_package", package_checks)

    check("15_cost_ledger", lambda: [CostRecord.model_validate(c) for c in load(AGENT / "15_cost_ledger.json")])

    # --- human feedback: exact gate resume-payload shapes -----------------
    def clarify():
        doc = load(HUMAN / "01_clarify_answers.json")
        assert isinstance(doc["answers"], list) and len(doc["answers"]) == 2
    check("clarify answers payload", clarify)

    def gate1_reject():
        doc = load(HUMAN / "02_strategy_gate_round1_reject.json")
        assert doc["action"] == "reject" and doc["notes"].strip()
    check("gate 1 reject payload", gate1_reject)

    def gate1_approve():
        doc = load(HUMAN / "03_strategy_gate_round2_approve.json")
        assert doc["action"] == "approve"
        assert set(doc["edits"]) <= set(Strategy.model_fields), "edits must patch Strategy fields"
        assert doc["edits"]["key_message"] == package.strategy.key_message
    check("gate 1 approve-with-edits payload", gate1_approve)

    def curation_ops():
        ops = load(HUMAN / "04_curation_session_ops.json")
        known_ids = set(directions)
        promoted_at = finalized_at = None
        for i, op in enumerate(ops):
            kind = op["op"]
            assert kind in KNOWN_OPS, f"unknown op {kind!r}"
            if "direction_id" in op:
                assert op["direction_id"] in known_ids, f"op {i} references unknown direction"
            if kind in ("edit", "regenerate_field"):
                assert op["field"] in EDITABLE_FIELDS, f"op {i} field {op['field']!r} not editable"
            if kind == "merge":
                assert len(op["direction_ids"]) >= 2
                assert set(op["field_choices"]) <= set(EDITABLE_FIELDS)
            if kind == "promote":
                promoted_at = i
            if kind == "finalize":
                finalized_at = i
        assert promoted_at is not None and finalized_at == len(ops) - 1
        assert promoted_at < finalized_at, "finalize requires a prior promotion"
    check("gate 2 curation ops", curation_ops)

    # --- deliverables: byte-identical to the repo's deterministic renderers
    def export_md():
        got = (DELIV / "export.md").read_text(encoding="utf-8")
        brief = Brief.model_validate(load(MOCK / "00_input_brief.json"))
        assert got == render_export_markdown([package], brief.brief)
    check("deliverables/export.md matches renderer", export_md)

    def tokens():
        assert load(DELIV / "tokens.json") == build_tokens_json(package)
        assert (DELIV / "tokens.css").read_text(encoding="utf-8") == build_tokens_css(package)
    check("deliverables/tokens.{json,css} match token service", tokens)

    print(f"\n{checked - len(errors)}/{checked} checks passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
