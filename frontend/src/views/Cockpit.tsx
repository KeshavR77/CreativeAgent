/**
 * Cockpit (§14.2) — the steering surface.
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
import type { ProjectView, Strategy } from '../api/types';

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
      className="flex flex-col gap-3 rounded-lg border border-amber-700 bg-slate-900 p-4"
    >
      <h2 className="text-lg font-semibold">Strategy approval (Gate 1)</h2>
      <p className="text-xs text-slate-400" data-project={projectId}>
        Approve the strategy (optionally with inline edits) or reject it with notes
        to re-run strategizing.
      </p>

      <label className="text-xs uppercase text-slate-400">Positioning</label>
      <textarea
        aria-label="Positioning"
        value={positioning}
        onChange={(e) => setPositioning(e.target.value)}
        rows={2}
        className="w-full rounded bg-slate-950 p-2 text-sm"
      />
      <label className="text-xs uppercase text-slate-400">Key message</label>
      <textarea
        aria-label="Key message"
        value={keyMessage}
        onChange={(e) => setKeyMessage(e.target.value)}
        rows={2}
        className="w-full rounded bg-slate-950 p-2 text-sm"
      />

      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onApprove(edits)}
          className="rounded bg-emerald-700 px-3 py-1 text-sm text-white disabled:opacity-40"
        >
          Approve{Object.keys(edits).length ? ' with edits' : ''}
        </button>
      </div>

      <div className="mt-2 flex flex-col gap-1">
        <label className="text-xs uppercase text-slate-400">Rejection notes</label>
        <textarea
          aria-label="Rejection notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded bg-slate-950 p-2 text-sm"
        />
        <button
          type="button"
          disabled={busy || !notes.trim()}
          onClick={() => onReject(notes.trim())}
          className="self-start rounded bg-rose-800 px-3 py-1 text-sm text-white disabled:opacity-40"
        >
          Reject & re-run
        </button>
      </div>
    </section>
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

  if (!id) return <main className="p-6 text-slate-100">No project selected.</main>;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6 text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Cockpit</h1>
        <RunStateChip state={state} />
      </div>
      <ModeBanner highTemp={highTemp} />
      {lastError ? (
        <p role="alert" className="rounded bg-rose-950 px-3 py-1 text-xs text-rose-200">
          {lastError}
        </p>
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
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300">
              Curation — steer the directions
            </h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={busy || mergeIds.length < 2}
                onClick={() => setMergeOpen(true)}
                className="rounded bg-slate-700 px-2 py-1 text-xs disabled:opacity-40"
              >
                Merge selected ({mergeIds.length})
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => run(() => api.finalize(id)).then(apply)}
                className="rounded bg-emerald-700 px-2 py-1 text-xs text-white disabled:opacity-40"
              >
                Finalize
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            {(view?.directions ?? []).map((d) => (
              <DirectionCard
                key={d.id}
                direction={d}
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

      {state !== 'awaiting_strategy_approval' && state !== 'awaiting_curation' ? (
        <p className="text-sm text-slate-400">
          This project is not currently awaiting a decision. Current state:{' '}
          <RunStateChip state={state} />
        </p>
      ) : null}
    </main>
  );
}
