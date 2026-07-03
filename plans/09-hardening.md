# Sub-plan 09 — Hardening (Masterplan Phase 6)

**Goal:** production-ready for its scope (localhost, single user): kill it anywhere and it
resumes; cancel cleanly; gates provably side-effect-free; errors recoverable via retry;
`make demo` and the full §18 acceptance script pass.

**Prerequisites:** 07-real-providers and 08-frontend.

## Scope

### Resumability (§9.5, §9.6)
- `startup_resume()` lifespan hook re-drives every `list_resumable()` registry row on boot.
- Send-branch idempotency: a completed direction (sketches already present) is **not**
  regenerated on resume; only the incomplete branch re-runs.
- `POST /projects/{id}/retry` (state=error only) re-runs from the last checkpoint.

### Cancellation (§9.5)
- `POST /cancel` → `task.cancel()`, registry `cancelled`, `run_cancelled` event; consistent
  state even when cancelled mid-fan-out (no orphaned tasks, no partial event corruption).

### Gate purity
- Verify no side effects before `interrupt()` in any gate node — re-entry from checkpoint
  must not duplicate events, writes, or provider calls.

### Ops polish
- `scripts/dev_seed.py` (`make demo`): seeds a project ready at Gate 2 for instant demos.
- Error envelope + 409 discipline audited across all routes; SSE heartbeat/reconnect verified
  under backend restart.

## Tests to author first (§16, Phase 6)
- `test_resume`: kill/restart at each RunState (incl. **mid-sketch-generation** — the branch
  completes post-restart; completed directions untouched); Gate-2 state intact after restart
  (cockpit view, regen ops, finalize all work).
- Gate purity test: gate node re-execution produces zero new events/writes before resume.
- Cancellation-during-fan-out test: cancel while K branches run → `cancelled` state, no
  further events, retry/restart behaves.

## Definition of Done (masterplan Phase 6 DoD + §18 acceptance)
- Phase-6 tests green; `make demo` works.
- Full §18 acceptance script passes:
  1. Keyless: `make setup`, dev servers, `make test`, `make e2e` all green.
  2. UI run of the sneaker brief (K=3) through every Gate-2 op to export.
  3. **Kill the backend at Gate 2 → restart → refresh: cockpit intact, sketch/moodboard
     regen + finalize still work.**
  4. With real keys: repeat with genuine sketches + hybrid moodboard, both kinds correctly
     attributed.
  5. `grep -r "sk-" --include="*.py" --include="*.ts" .` → nothing; `.env`, `data/` untracked.

## Out of scope
Multi-user/auth/deployment (explicit non-goals, §2); Postgres swap (kept possible by narrow
repos, not exercised).

## Traps (§19)
- Resume double-firing provider calls — idempotency lives in checkpoint discipline, not in
  ad-hoc "already done" flags.
- Registry state drifting from graph state — the runner's node→RunState map is the single
  writer.
