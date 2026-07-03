# Sub-plan 03 — Graph spine & Gate 1 (Masterplan Phase 2)

**Goal:** the walking skeleton. A checkpointed LangGraph run goes brief → interrogate →
research → strategize → **strategy_gate** (blocking human interrupt) → verbal → briefwrite →
seed, driven by the RunManager, observable over SSE, entirely on mocks.

**Prerequisites:** 02-domain-storage.

## Scope

### Mock model layer first (§8.1, §8.2, §8.4, §8.5)
- `services/models.py` — `get_chat_model(role, *, temperature) -> BaseChatModel`; mock when
  `ANTHROPIC_API_KEY` empty. Critic role resolves `CRITIC_MODEL` (real-vs-real assertion
  arrives in sub-plan 07).
- `services/mock_chat.py` — `MockChatModel(BaseChatModel)`: deterministic (seed = project_id +
  role + territory label); territory label appears in outputs so mock runs have measurable
  divergence later.
- Structured output via `with_structured_output(..., include_raw=True)`; **repair loop**
  (§8.4): one repair call stripping ``` fences; second failure → `AgentOutputError` (node
  fails; RetryPolicy excludes it).
- `services/search.py` — Tavily interface backed by `mock_search_corpus.json` when keyless.

### Spine nodes (§10.1–10.6)
- `interrogate`, `research`, `strategize`, `verbal`, `briefwrite`, `seed` in `graph/nodes/`.
- Prompts as `prompts/*.md` with `{{placeholder}}` templating; each node: load prompt →
  `get_chat_model` → structured output → validate → return delta; emit
  `agent_started/completed` + `artifact_written`; append `CostRecord`.
- Optional `clarify` interrupt behind `ASK_CLARIFYING_QUESTIONS`.

### Graph build & Gate 1 (§9.1, §9.4, §12.1)
- `graph/build.py`: `StateGraph(GraphState)` compiled **with** `AsyncSqliteSaver` — never
  without. Invoke config `{"configurable": {"thread_id": project_id}}`, `durability="sync"`.
- `graph/gates.py`: `strategy_gate` — `interrupt(...)` is the **first statement**; resume with
  `Command`: approve (with optional edits → `edited_by_human=True`) → `verbal`; reject (with
  notes → `rejection_notes`) → back to `strategize`.
- Provider-calling nodes get `retry_policy=RetryPolicy(max_attempts=3, retry_on=<transient only>)`.

### Runner — the only glue (§9.6, §6.3)
- `graph/runner.py` `RunManager` singleton: compiled graph + `{project_id: asyncio.Task}` +
  per-project `asyncio.Lock`; `start`, `resume` (under the lock), `_drive` translating
  `astream(..., stream_mode=["updates","messages","custom"], durability="sync")` into events
  persisted via `EventRepo.append` → pub/sub → SSE. **All durable event writes happen here
  only**; nodes never write the DB directly.
- Node→RunState mapping + `__interrupt__.gate` → `awaiting_*`; cached in the registry.

### API (§13, spine subset)
- `POST /projects`, `GET /projects`, `GET /projects/{id}` (view composed in `models/views.py`:
  registry row + `graph.aget_state(config).values` + current interrupt payload),
  `POST /projects/{id}/start`, `POST /projects/{id}/clarify`,
  `POST /projects/{id}/gates/strategy` (§12.1), `GET /projects/{id}/events` (SSE:
  `id:`=seq, `event:`=type, `Last-Event-ID` backfill, 15s heartbeat, `agent_token`
  pre-batched).

## Tests to author first (§16)
- `test_graph_spine`: mock run reaches `strategy_gate` and pauses (`awaiting_strategy_approval`);
  approve → continues through `seed` writing `verbal_identity`, `creative_brief`,
  `territories`; reject-with-notes → re-runs `strategize` and re-interrupts; state persists
  across a fresh graph instance pointed at the same `thread_id` (checkpointer proof).
- SSE part of `test_api`: event ordering by seq, `Last-Event-ID` backfill, gate_reached/
  gate_resolved emission, run_state_changed transitions.
- `test_repair`: invalid JSON → one repair → success; double failure → `AgentOutputError`.

## Definition of Done (masterplan Phase 2 DoD)
- Above tests green with zero keys; spine runs through `strategy_gate` with checkpointer,
  RunManager, SSE, and Gate-1 endpoints working.

## Out of scope
Fan-out/`Send`, curation gate, sketches/moodboard, divergence, export, real providers.

## Traps (§19)
- **No side effects before `interrupt()`** in gate nodes — gates re-execute on resume.
- Never compile without the checkpointer; never invoke without `thread_id`.
- Don't stream every token as its own SSE event — batch `agent_token`.
- Don't let the creative brief prescribe visuals (§10.5 validation).
