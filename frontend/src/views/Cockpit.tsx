/**
 * Cockpit — the steering surface.
 *   - Gate 1 (awaiting_strategy_approval): StrategyGatePanel — approve with inline
 *     edits, or reject with notes.
 *   - Gate 2 (awaiting_curation): a DirectionCard per direction (editable fields,
 *     divergence + critique badges, promote/kill/fork/merge-select, sketch &
 *     moodboard regeneration), plus the MergeModal.
 * Every op goes through the typed client under a per-project op-lock, so actions
 * disable mid-flight and a 409 (wrong state) is surfaced rather than corrupting UI.
 */
import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useProjectStore, routeForState } from '../store/useProjectStore';
import { useProjectSync } from '../store/useProjectSync';
import { useOpLock } from '../store/useOpLock';
import { ModeBanner } from '../components/ModeBanner';
import { RunStateChip } from '../components/RunStateChip';
import { DirectionCard } from '../components/DirectionCard';
import { MergeModal } from '../components/MergeModal';
import { Shell } from '../components/Shell';
import type { IdeaReview, ProjectView, Strategy, Territory } from '../api/types';

function StrategyGatePanel({
  projectId,
  strategy,
  busy,
  onApprove,
  onReject,
}: {
  projectId: string;
  strategy: Strategy | null;
  busy: boolean;
  onApprove: (edits: Record<string, unknown>) => void;
  onReject: (notes: string) => void;
}) {
  const [positioning, setPositioning] = useState(strategy?.positioning ?? '');
  const [keyMessage, setKeyMessage] = useState(strategy?.key_message ?? '');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    setPositioning(strategy?.positioning ?? '');
    setKeyMessage(strategy?.key_message ?? '');
  }, [strategy]);

  const edits: Record<string, unknown> = {};
  if (strategy && positioning !== strategy.positioning) edits.positioning = positioning;
  if (strategy && keyMessage !== strategy.key_message) edits.key_message = keyMessage;

  return (
    <section
      data-testid="strategy-gate-panel"
      className="panel flex flex-col gap-5 border-l-2 border-l-warn p-8"
    >
      <header>
        <p className="kicker mb-1">Gate 1 — human decision</p>
        <h2 className="font-serif text-2xl text-ink">Strategy approval</h2>
        <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-muted" data-project={projectId}>
          Approve the strategy (optionally with inline edits) or reject it with notes
          to re-run strategizing.
        </p>
      </header>

      <div className="flex flex-col gap-1.5">
        <label className="kicker" htmlFor="gate-positioning">
          Positioning
        </label>
        <textarea
          id="gate-positioning"
          aria-label="Positioning"
          value={positioning}
          onChange={(e) => setPositioning(e.target.value)}
          rows={4}
          className="field font-serif text-[16px]"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="kicker" htmlFor="gate-key-message">
          Key message
        </label>
        <textarea
          id="gate-key-message"
          aria-label="Key message"
          value={keyMessage}
          onChange={(e) => setKeyMessage(e.target.value)}
          rows={2}
          className="field font-serif text-[16px]"
        />
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onApprove(edits)}
          className="btn-ink"
        >
          Approve{Object.keys(edits).length ? ' with edits' : ''}
        </button>
      </div>

      <div className="flex flex-col gap-1.5 border-t border-line pt-5">
        <label className="kicker" htmlFor="gate-notes">
          Rejection notes
        </label>
        <textarea
          id="gate-notes"
          aria-label="Rejection notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="field"
        />
        <button
          type="button"
          disabled={busy || !notes.trim()}
          onClick={() => onReject(notes.trim())}
          className="btn-danger self-start"
        >
          Reject & re-run
        </button>
      </div>
    </section>
  );
}

function IdeationGatePanel({
  projectId,
  territories,
  reviews,
  busy,
  onSubmit,
  onProceed,
}: {
  projectId: string;
  territories: Territory[];
  reviews: IdeaReview[];
  busy: boolean;
  onSubmit: (ideasText: string) => void;
  onProceed: () => void;
}) {
  const [ideasText, setIdeasText] = useState('');

  return (
    <section
      data-testid="ideation-gate-panel"
      className="panel flex flex-col gap-6 border-l-2 border-l-warn p-8"
    >
      <header>
        <p className="kicker mb-1">Ideation — human decision</p>
        <h2 className="font-serif text-2xl text-ink">Brainstorm with your studio of choice</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted">
          Download the ideation packet and take it to any external creative model or
          agent. Paste its output back here — each idea gets an independent critique
          so you can iterate — then proceed to build on the ideas you keep.
          Proceeding with nothing submitted lets the in-house model ideate instead.
        </p>
      </header>

      <div className="flex flex-wrap items-baseline gap-3">
        <a href={api.ideationPacketUrl(projectId)} download className="btn-ink">
          Download ideation packet
        </a>
        <span className="font-mono text-[10px] uppercase tracking-kicker text-muted">
          {territories.length} territories
        </span>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="kicker" htmlFor="ideas-paste">
          Paste the brainstorm output
        </label>
        <textarea
          id="ideas-paste"
          aria-label="External ideas"
          value={ideasText}
          onChange={(e) => setIdeasText(e.target.value)}
          rows={7}
          placeholder={`### ${territories[0]?.label ?? 'Territory'}\nThe big idea…`}
          className="field font-mono text-[12px]"
        />
        <button
          type="button"
          disabled={busy || !ideasText.trim()}
          onClick={() => onSubmit(ideasText)}
          className="btn-ghost self-start"
        >
          Submit for critique
        </button>
      </div>

      {reviews.length > 0 ? (
        <div className="flex flex-col gap-4 border-t border-line pt-5" data-testid="idea-reviews">
          <p className="kicker">In-house critique — iterate or proceed</p>
          {reviews.map((r, i) => (
            <div key={`${r.territory_label}-${i}`} className="flex flex-col gap-1.5 border-l-2 border-line pl-4">
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="font-serif text-[15px] text-ink">{r.territory_label}</span>
                <span
                  className={`font-mono text-[10px] uppercase tracking-kicker ${
                    r.score >= 4 ? 'text-ok' : r.score >= 3 ? 'text-warn' : 'text-accent'
                  }`}
                >
                  score {r.score.toFixed(1)}
                </span>
              </div>
              <p className="text-[14px] leading-relaxed text-ink">{r.big_idea}</p>
              {r.case_for ? (
                <p className="text-[12px] leading-relaxed text-muted">
                  <span className="text-ok">for</span> — {r.case_for}
                </p>
              ) : null}
              {r.case_against ? (
                <p className="text-[12px] leading-relaxed text-muted">
                  <span className="text-accent">against</span> — {r.case_against}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex items-center gap-3 border-t border-line pt-5">
        <button type="button" disabled={busy} onClick={onProceed} className="btn-ink">
          Proceed to exploration
        </button>
        <span className="text-[12px] text-muted">
          {reviews.length
            ? 'builds on the submitted ideas (best score per territory wins)'
            : 'nothing submitted — the in-house model will ideate'}
        </span>
      </div>
    </section>
  );
}


function ProcessRecord({ view }: { view: ProjectView }) {
  const rows: { label: string; body: React.ReactNode }[] = [];
  if (view.brief) {
    rows.push({
      label: '01 Brief',
      body: (
        <>
          <p className="text-[14px] leading-relaxed text-ink">{view.brief.brief}</p>
          {view.brief.audience ? (
            <p className="mt-1 font-mono text-[10px] text-muted">audience — {view.brief.audience}</p>
          ) : null}
          {view.brief.constraints?.length ? (
            <p className="font-mono text-[10px] text-muted">constraints — {view.brief.constraints.join(' · ')}</p>
          ) : null}
        </>
      ),
    });
  }
  if (view.research?.summary) {
    rows.push({
      label: '02 Research',
      body: (
        <>
          <p className="text-[14px] leading-relaxed text-ink">{view.research.summary}</p>
          {view.research.competitors?.length ? (
            <p className="mt-1 font-mono text-[10px] text-muted">
              competitors — {view.research.competitors.map((c) => c.name).join(' · ')}
            </p>
          ) : null}
        </>
      ),
    });
  }
  if (view.strategy) {
    rows.push({
      label: '03 Strategy',
      body: (
        <>
          <p className="font-serif text-[15px] leading-snug text-ink">{view.strategy.positioning}</p>
          <p className="mt-1 text-[13px] italic text-muted">{view.strategy.key_message}</p>
          {view.strategy.pillars?.length ? (
            <p className="mt-1 font-mono text-[10px] text-muted">pillars — {view.strategy.pillars.join(' · ')}</p>
          ) : null}
        </>
      ),
    });
  }
  if (view.verbal_identity) {
    rows.push({
      label: '04 Verbal identity',
      body: (
        <>
          <p className="text-[14px] text-ink">
            {view.verbal_identity.tagline}
            <span className="ml-2 font-mono text-[10px] text-muted">tone — {view.verbal_identity.tone}</span>
          </p>
          {view.verbal_identity.names?.length ? (
            <p className="mt-1 flex flex-wrap items-center gap-2">
              {view.verbal_identity.names.map((n) => (
                <span key={n} className="rounded-sm border border-line px-1.5 py-0.5 text-xs text-ink">
                  {n}
                </span>
              ))}
              <span className="rounded-sm bg-accent-soft px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-kicker text-accent">
                unscreened
              </span>
            </p>
          ) : null}
        </>
      ),
    });
  }
  if (view.creative_brief) {
    rows.push({
      label: '05 Creative brief',
      body: (
        <>
          <p className="text-[14px] leading-relaxed text-ink">{view.creative_brief.objective}</p>
          <p className="mt-1 font-mono text-[10px] text-muted">
            key message — {view.creative_brief.key_message}
            {view.creative_brief.mandatories?.length
              ? ` · mandatories — ${view.creative_brief.mandatories.join(' · ')}`
              : ''}
          </p>
        </>
      ),
    });
  }
  if (view.territories?.length) {
    rows.push({
      label: '06 Territories',
      body: (
        <div className="flex flex-col gap-1.5">
          {view.territories.map((t, ti) => (
            <p key={`${t.label}-${ti}`} className="text-[13px] leading-relaxed text-ink">
              <span className="font-serif">{t.label}</span>
              <span className="text-muted"> — {t.lens}</span>
            </p>
          ))}
        </div>
      ),
    });
  }
  if (!rows.length) return null;
  return (
    <details data-testid="process-record" className="panel group px-6 py-4">
      <summary className="flex cursor-pointer list-none items-baseline gap-3 [&::-webkit-details-marker]:hidden">
        <span className="kicker">Process record</span>
        <span className="font-mono text-[10px] text-faint">
          the approved steps behind these directions
        </span>
        <span className="ml-auto font-mono text-[10px] text-muted transition-transform group-open:rotate-90">
          ▸
        </span>
      </summary>
      <div className="mt-4 flex flex-col gap-5 border-t border-line pt-4">
        {rows.map((r) => (
          <div key={r.label} className="flex flex-col gap-1">
            <span className="kicker">{r.label}</span>
            {r.body}
          </div>
        ))}
      </div>
    </details>
  );
}

export default function Cockpit() {
  const { id } = useParams();
  const navigate = useNavigate();
  useProjectSync(id);

  const view = useProjectStore((s) => s.view) as ProjectView | null;
  const { busy, lastError, run } = useOpLock();
  const [mergeIds, setMergeIds] = useState<string[]>([]);
  const [mergeOpen, setMergeOpen] = useState(false);

  const state = view?.state ?? 'intake';
  const highTemp = (view?.directions ?? []).some((d) => d.brain === 'claude_high_temp');

  // Route away once the gate is resolved and the run moves on.
  useEffect(() => {
    if (!id || !view) return;
    const target = routeForState(view.state, id);
    if (target !== `/cockpit/${id}`) navigate(target);
  }, [id, view, navigate]);

  const apply = (updated: ProjectView | undefined) => {
    if (updated) useProjectStore.getState().setView(updated);
  };

  const selectedForMerge = useMemo(() => new Set(mergeIds), [mergeIds]);
  const toggleMerge = (did: string) =>
    setMergeIds((prev) =>
      prev.includes(did) ? prev.filter((x) => x !== did) : [...prev, did]
    );

  const mergeDirections = (view?.directions ?? []).filter((d) => mergeIds.includes(d.id));

  if (!id)
    return (
      <Shell surface="Cockpit">
        <p className="text-sm text-muted">No project selected.</p>
      </Shell>
    );

  return (
    <Shell surface="Cockpit" right={<RunStateChip state={state} />} wide>
      <div className="flex flex-col gap-6">
        <ModeBanner highTemp={highTemp} />
        {lastError ? (
          <p
            role="alert"
            className="rounded-sm border border-accent/30 bg-accent-soft px-3 py-2 font-mono text-[11px] text-accent"
          >
            {lastError}
          </p>
        ) : null}

        {view && (state === 'awaiting_curation' || state === 'awaiting_ideation') ? (
          <ProcessRecord view={view} />
        ) : null}

        {view && state === 'awaiting_ideation' ? (
          <IdeationGatePanel
            projectId={id}
            territories={view.territories ?? []}
            reviews={((view.interrupt?.reviews as IdeaReview[] | undefined) ?? []) as IdeaReview[]}
            busy={busy}
            onSubmit={(ideasText) =>
              run(() => api.resolveIdeationGate(id, { action: 'submit', ideas_text: ideasText })).then(
                apply
              )
            }
            onProceed={() =>
              run(() => api.resolveIdeationGate(id, { action: 'proceed' })).then(apply)
            }
          />
        ) : null}

        {state === 'awaiting_strategy_approval' ? (
          <StrategyGatePanel
            projectId={id}
            strategy={view?.strategy ?? null}
            busy={busy}
            onApprove={(edits) =>
              run(() => api.resolveStrategyGate(id, { action: 'approve', edits })).then(apply)
            }
            onReject={(notes) =>
              run(() => api.resolveStrategyGate(id, { action: 'reject', notes })).then(apply)
            }
          />
        ) : null}

        {state === 'awaiting_curation' ? (
          <>
            <div className="flex items-baseline justify-between border-b border-line pb-4">
              <div>
                <p className="kicker mb-1">Gate 2 — human decision</p>
                <h2 className="font-serif text-2xl text-ink">
                  Curation — steer the directions
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={busy || mergeIds.length < 2}
                  onClick={() => setMergeOpen(true)}
                  className="btn-ghost"
                >
                  Merge selected ({mergeIds.length})
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => api.finalize(id)).then(apply)}
                  className="btn-ink"
                >
                  Finalize
                </button>
              </div>
            </div>

            <div className="flex flex-col gap-8">
              {(view?.directions ?? []).map((d) => (
                <DirectionCard
                  key={d.id}
                  direction={d}
                  names={view?.verbal_identity?.names}
                  busy={busy}
                  mergeSelected={selectedForMerge.has(d.id)}
                  onToggleMerge={toggleMerge}
                  onPromote={(did) => run(() => api.promote(id, did)).then(apply)}
                  onKill={(did) => run(() => api.kill(id, did)).then(apply)}
                  onFork={(did) => run(() => api.fork(id, did)).then(apply)}
                  onRecritique={(did) => run(() => api.recritique(id, did)).then(apply)}
                  onEditField={(did, payload) =>
                    run(() => api.editField(id, did, payload.field, payload.value)).then(apply)
                  }
                  onRegenerateField={(did, field) =>
                    run(() => api.regenerateField(id, did, field)).then(apply)
                  }
                  onRegenerateSketch={(did, index) =>
                    run(() => api.regenerateSketch(id, did, index)).then(apply)
                  }
                  onRegenerateAllSketches={(did) =>
                    run(() => api.regenerateSketches(id, did)).then(apply)
                  }
                  onRegenerateMoodboardItem={(did, args) =>
                    run(() =>
                      api.regenerateMoodboardItem(id, did, args.index, args.kind)
                    ).then(apply)
                  }
                />
              ))}
            </div>

            {mergeOpen ? (
              <MergeModal
                directions={mergeDirections}
                onClose={() => setMergeOpen(false)}
                onMerge={async (body) => {
                  await run(() =>
                    api.merge(id, body.direction_ids, body.field_choices)
                  ).then(apply);
                  setMergeOpen(false);
                  setMergeIds([]);
                }}
              />
            ) : null}
          </>
        ) : null}

        {state !== 'awaiting_strategy_approval' &&
        state !== 'awaiting_ideation' &&
        state !== 'awaiting_curation' ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            This project is not currently awaiting a decision. Current state:{' '}
            <RunStateChip state={state} />
          </p>
        ) : null}
      </div>
    </Shell>
  );
}
