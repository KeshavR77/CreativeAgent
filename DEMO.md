# Demo runbook — Madin (design brand agency)

**The one workflow:** drop a client RFP PDF, and the platform runs the whole
engagement in front of them — reads the RFP, drafts the brief, researches,
proposes strategy (human gate), explores creative directions with real generated
imagery, lets you curate like a creative director, and exports a concept package.
One live take, no seeded/fake data, everything real on GLM-5.2 + glm-image.

---

## 0. Pre-demo checklist (10 minutes before)

```bash
cd /Users/chetanraghavan/Desktop/Projects/CreativeAgent

# 1. Exactly one backend, env loaded from .env in THIS shell:
pkill -9 -f "uvicorn app.main:app" 2>/dev/null; sleep 1
set -a; . ./.env; set +a
PYTHONPATH=backend nohup backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 > scratch_backend.log 2>&1 &

# 2. Frontend:
cd frontend && npm run dev &   # http://localhost:5173
cd ..

# 3. Health — MUST show claude:"real" and image_gen provider "zai":
curl -s http://127.0.0.1:8000/api/health

# 4. Warm-up GLM call (also warms the connection):
backend/.venv/bin/python -c "
from langchain_anthropic import ChatAnthropic
print(ChatAnthropic(model='glm-5.2', max_retries=1, timeout=30).invoke('pong?').content)"
```

- Open http://localhost:5173 — you should see **Drop the client RFP** and an empty
  History (no fake projects).
- **Do one full real run before the meeting** so History holds a finished example
  (your safety net — see §2). `MockBrief.pdf` (a real Cerebelly RFP) is in the repo
  root and works end to end.
- Have the RFP PDF ready on the desktop. Ask Madin to bring one of *their* real
  RFPs if they're willing — dropping their own document is the most convincing beat.

## 1. The take (12–15 minutes)

| Beat | Do | Say |
|---|---|---|
| Drop the RFP (30s) | Drag the client RFP PDF onto the drop zone (or click to pick). The button shows "Reading the RFP…". | "You hand it the client's RFP exactly as it arrives — a multi-page PDF. It reads it and drafts the brief." |
| Brief understood (~10s) | It distills the RFP into a brief + audience + constraints, creates the project, and jumps to the live theater. | "It pulled the positioning challenge, the audience, and the hard constraints — the substantiation requirements, the mandatories — straight out of the document." |
| Live theater (~40s) | Studio: numbered pipeline lights up, agent stream narrates research → strategy, cost footer ticks. | "Research, then strategy — every provider call metered, nothing hidden." |
| **Gate 1** (2 min) | It stops. Read the strategy aloud. **Edit the key message inline**, then Approve. (Weak? Reject with notes — it re-runs in ~15s. That's a flex.) | "It won't spend the client's money exploring a strategy no human signed off. Taste is a gate, not a garnish." |
| Exploration (~6–8 min) | Studio: K=3 territory lanes appear immediately as pulsing skeletons, then fill with ideas, copy, art direction, and **real generated sketches + 9-tile moodboards**. This is the **talking window** (below). | "Three creative territories in parallel. Every image generated fresh — no stock, no placeholders. Each direction is then critiqued by a *different* model than the one that had the idea." |
| **Gate 2 — Cockpit** (4 min) | The centerpiece. Open the **Process record** to show brief→strategy→identity lineage. Then steer: **edit** a headline → critique goes stale → **re-critique**; **regenerate** a tile; **fork** the strongest; **kill** the weakest; select two → **merge** (pick fields per parent); **promote** the winner. | "This is what every AI tool gets wrong — it's not accept/reject. You steer at the granularity of a single field. Kill, fork, merge — a creative director, not a slot machine." |
| Finalize → Export (2 min) | Finalize. Export page: concept package — strategy, big idea, sketches, moodboard with per-tile provenance, copy. Download `export.md` + `tokens.css`. Point at the AI-disclosure block and "unscreened" badge. | "Honest handoff: every image tagged, names flagged unscreened, design tokens ready for a designer to pick up." |

**Talking window during exploration (pick 2):**
- Cost ledger: a full concept round is single-digit dollars, not a pitch team's week.
- Critic independence: generator `glm-5.2`, critic `glm-4.7` — enforced in code.
- Divergence: an embeddings measure that the 3 directions are genuinely *different*.
- The vision for Madin: their taste and process, encoded as the gates — the platform
  does the volume, they keep the judgment.

## 2. If something breaks live

| Symptom | Move |
|---|---|
| Exploration slow / a z.ai image is slow | Keep talking — each image retries hard and the board fills with real tiles (never placeholders). |
| A direction failed entirely | "The run isolates a failed branch — the others land." Steer the survivors. |
| GLM/API outage mid-run | Open your **pre-run finished project** from History → do the Cockpit + Export beats there. Loses the live reveal, keeps the substance. |
| Backend dies | The graph is checkpointed — restart the backend (§0) and the project resumes at its gate. Say exactly that; durability is a feature. |
| A PDF won't read (scanned image) | It returns a clear message. Use the "or type a brief instead" path, or drop `MockBrief.pdf`. |

## 3. Numbers (from real runs, 2026-07)

- Drop RFP → brief drafted: **~10–20 seconds** (GLM reads the whole RFP).
- Brief → Gate 1: **~15 seconds**.
- Gate 1 → curation gate: **~6–8 minutes** (3 directions × [idea, spec, copy,
  critique] + 12 real image generations each; slow z.ai streams self-heal via
  120 s timeouts + retries).
- Cost: **≈ 30–60k tokens + ~40 images** per full run on z.ai pricing — cents.
- Plan the meeting around it: drop + Gate 1 live, exploration window IS the vision
  pitch (~7 min of material), then Cockpit → Export.

## 4. What's real vs mock

- **Real (GLM-5.2 / glm-image):** RFP reading, research, strategy, naming, brief,
  ideation, copy, art direction, critique, and every sketch/moodboard image.
- **Mock/off (no keys, fine):** web search and Pexels sourcing. The moodboard is
  therefore all AI-generated — still real images, just no stock lane. No placeholders.
