"""Hybrid moodboard service tests (Stage 05, §8.7/§16).

Hybrid by construction (generated + sourced within rounding); a downed lane
redirects its share to the live one to reach `size`; both down → all placeholders;
kind-swap regen updates the slot's lane + provenance; provenance-incomplete refs
are dropped and the board is backfilled to `size`.
"""

from __future__ import annotations

from app.services import moodboard

MOODS = ["earthy", "honest", "grounded"]
IMAGERY = "raw natural materials in muted tones"


def _kinds(board):
    return [r.kind for r in board]


def _provenance_ok(board) -> bool:
    for r in board:
        if r.kind == "generated" and not (r.gen_model and r.gen_prompt):
            return False
        if r.kind == "sourced" and not (r.source_url and r.attribution):
            return False
    return True


def test_hybrid_both_lanes_ratio_split(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")

    assert len(board) == 9  # MOODBOARD_SIZE
    assert {"generated", "sourced"} <= set(_kinds(board))  # genuinely hybrid
    assert _kinds(board).count("generated") == 3  # round(9 * 0.34)
    assert _kinds(board).count("sourced") == 6
    assert _provenance_ok(board)


def test_source_disabled_redirects_to_all_generated(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")  # source lane off
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")
    assert len(board) == 9
    assert all(r.kind == "generated" for r in board)
    assert _provenance_ok(board)


def test_gen_disabled_redirects_to_all_sourced(clean_env) -> None:
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")  # gen lane off
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")
    assert len(board) == 9
    assert all(r.kind == "sourced" for r in board)
    assert _provenance_ok(board)


def test_both_disabled_all_placeholders(clean_env) -> None:
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")
    assert len(board) == 9
    assert all(r.kind == "placeholder" for r in board)


def test_kind_swap_regen_updates_lane_and_provenance(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")
    gi = next(i for i, r in enumerate(board) if r.kind == "generated")

    swapped = moodboard.regenerate_slot(board, gi, "dir1", MOODS, IMAGERY, project_id="p1", kind="sourced")

    assert len(swapped) == len(board)
    assert swapped[gi].kind == "sourced"
    assert swapped[gi].source_url and swapped[gi].attribution  # provenance for the new kind
    assert all(swapped[j] == board[j] for j in range(len(board)) if j != gi)  # others untouched


def test_provenance_incomplete_dropped_and_backfilled(clean_env, monkeypatch) -> None:
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")  # all-sourced target
    from app.services import imagesource

    real_search = imagesource.search

    def short_search(query, n):
        # simulate most refs being dropped for incomplete provenance
        return real_search(query, n)[:2]

    monkeypatch.setattr(imagesource, "search", short_search)
    board = moodboard.build("dir1", MOODS, IMAGERY, project_id="p1")

    assert len(board) == 9  # backfilled to size despite the shortfall
