# Demo runbook — Madin (design brand agency)

**The one workflow:** a single live take, brief → export, on GLM-5.2 with real
image generation. No mocks, no pre-canned slides — the platform does the work in
front of them, with two pre-staged projects in History as silent insurance.

---

## 0. Pre-demo checklist (10 minutes before)

```bash
cd /Users/chetanraghavan/Desktop/Projects/CreativeAgent

# 1. Exactly one backend, with the env loaded from .env in THIS shell:
pkill -9 -f "uvicorn app.main:app" 2>/dev/null; sleep 1
set -a; . ./.env; set +a
PYTHONPATH=backend nohup backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 > scratch_backend.log 2>&1 &

# 2. Frontend:
cd frontend && npm run dev &   # http://localhost:5173

# 3. Health — MUST show claude:"real" and image_gen zai:
curl -s http://127.0.0.1:8000/api/health

# 4. One warm-up GLM call (also warms the connection):
cd .. && backend/.venv/bin/python -c "
from langchain_anthropic import ChatAnthropic
print(ChatAnthropic(model='glm-5.2', max_retries=1, timeout=30).invoke('pong?').content)"
```

- Open http://localhost:5173 — History should show the two insurance projects
  (one parked at curation, one finished with an export).
- Keep this terminal visible on a second desktop for the health check only;
  everything else happens in the browser.

## 1. The take (12–15 minutes)

| Beat | Do | Say |
|---|---|---|
| Brief (30s) | Type a brief **from Madin's world** (ask them for one, or use: "Launch a sustainable sneaker brand for runners who are sick of greenwashing"). Create & start. | "You give it a brief the way a client gives you one — underspecified." |
| Live theater (~40s) | Studio: numbered pipeline lights up, agent stream narrates, cost footer ticks. | "Research, then strategy — every provider call is metered, nothing hidden." |
| **Gate 1** (2 min) | The run *stops*. Read the strategy aloud. **Edit the key message inline**, then Approve. (If it's genuinely weak: Reject with notes — it re-runs in ~15s. That's a flex, not a failure.) | "The system won't spend your money exploring a strategy you haven't signed. Human taste is a gate, not a garnish." |
| Exploration (~6–8 min) | Studio again: K=3 territory lanes appear immediately as pulsing skeletons, then fill in as branches land — ideas, copy, art direction, real generated sketches + 9-tile moodboards. **This is the talking window** (see below). | "Three creative territories in parallel. Every image is generated fresh — watch the tiles land. Each direction then gets critiqued by a *different* model — the critic can't be the same brain that had the idea." |
| **Gate 2 — Cockpit** (4 min) | The centerpiece. Per direction: critique scores + case-against; divergence score. Then steer: **edit** a headline → critique goes stale → **re-critique**; **regenerate** one weak moodboard tile; **fork** the best direction; **kill** the weakest (it greys out); select two → **merge** (pick fields per parent); **promote** the winner. | "This is the part every AI tool gets wrong — it's not accept/reject. You steer at the granularity of a single field. Kill, fork, merge — like a creative director, not a slot machine." |
| Finalize → Export (2 min) | Finalize. Export page: concept package — strategy, big idea, sketches, moodboard with per-tile provenance, copy. Download `export.md` + `tokens.css`. Point at the AI-disclosure block and "unscreened" badge. | "The handoff is honest: every image tagged generated vs sourced, names flagged unscreened, design tokens ready for a designer to take over." |

**Talking window during exploration (choose 2):**
- Cost ledger: "a full concept round costs single-digit dollars, not a pitch team's week."
- Critic independence: generator glm-5.2, critic glm-4.7 — enforced in code.
- Divergence: embeddings-based measure that the 3 directions are actually
  *different*, not one idea in three fonts.
- The vision for Madin: their taste, their process, encoded as gates — the
  platform does the volume, they do the judgment.

## 2. Insurance (if anything breaks live)

| Symptom | Move |
|---|---|
| Exploration slow/images 429 | Keep talking over it (it recovers — per-image retry + placeholder degradation). Placeholder tiles have a ⟳ — regenerate one live: "nothing is precious." |
| A direction failed entirely | "The run isolates a failed branch — the others land." Then kill/fork narrative on the survivors. |
| GLM/API outage | Open the **parked insurance project** from History → do the full Cockpit + Export beats there. The story loses 90s of liveness, none of the substance. |
| Backend dies | The graph is checkpointed: restart the backend (step 0 command); the project resumes at its gate. Say exactly that — durability is a feature. |

## 3. Reset between runs (if you demo twice)

Nothing to reset — each run is a new project. To hide clutter, the History list
is ordered newest-first; old runs just scroll down.

## 4. Numbers that land (from tonight's rehearsals)

- Brief → Gate 1: **~15 seconds** (research + strategy on glm-5.2)
- Gate 1 → curation gate: **~6–8 minutes** (3 directions × [idea, spec, copy,
  critique] + 12 real image generations each; z.ai streams can stall — the
  clients time out at 120 s and retry, so a slow patch self-heals)
- Cost: **≈ 30–60k tokens + ~40 images** per full run on z.ai pricing — cents.
- Plan the meeting around it: brief + Gate 1 live, then the exploration window
  IS your vision pitch (7 minutes of talking material), then Cockpit → Export.
