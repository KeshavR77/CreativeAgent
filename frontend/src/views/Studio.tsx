/**
 * Studio (§14.1) — the live theater. Binds the project to the store (SSE + view
 * rehydrate), then renders:
 *   - PipelineSpine: node-by-node progress driven by RunState.
 *   - AgentStream: the batched agent-token transcript from the store.
 *   - LaneGrid: skeleton cards that fill in as `direction_created` arrives.
 *   - CostFooter: running provider cost/usage.
 *   - ModeBanner + a distinct claude_high_temp ideator badge.
 * When a gate is reached it routes to the Cockpit; when done, to Export.
 */
import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProjectStore, routeForState } from '../store/useProjectStore';
import { useProjectSync } from '../store/useProjectSync';
import { ModeBanner } from '../components/ModeBanner';
import { RunStateChip } from '../components/RunStateChip';
import type { RunState } from '../api/types';

const PIPELINE: { key: RunState; label: string }[] = [
  { key: 'intake', label: 'Intake' },
  { key: 'interrogating', label: 'Interrogate' },
  { key: 'researching', label: 'Research' },
  { key: 'strategizing', label: 'Strategy' },
  { key: 'awaiting_strategy_approval', label: 'Gate 1' },
  { key: 'naming', label: 'Naming' },
  { key: 'briefing', label: 'Brief' },
  { key: 'seeding', label: 'Seed' },
  { key: 'exploring', label: 'Explore' },
  { key: 'diverging', label: 'Diverge' },
  { key: 'awaiting_curation', label: 'Gate 2' },
  { key: 'refining', label: 'Refine' },
  { key: 'packaging', label: 'Package' },
  { key: 'done', label: 'Done' },
];

function PipelineSpine({ state }: { state: RunState | string }) {
  const activeIndex = PIPELINE.findIndex((p) => p.key === state);
  return (
    <ol data-testid="pipeline-spine" className="flex flex-wrap gap-1">
      {PIPELINE.map((node, i) => {
        const done = activeIndex > i;
        const active = activeIndex === i;
        return (
          <li
            key={node.key}
            data-active={active}
            data-done={done}
            className={`rounded px-2 py-0.5 text-[10px] ${
              active
                ? 'bg-sky-600 text-white'
                : done
                  ? 'bg-slate-700 text-slate-300'
                  : 'bg-slate-900 text-slate-500'
            }`}
          >
            {node.label}
          </li>
        );
      })}
    </ol>
  );
}

function AgentStream({ text }: { text: string }) {
  return (
    <pre
      data-testid="agent-stream"
      className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950 p-2 text-xs text-slate-300"
    >
      {text || '…waiting for the agents to start…'}
    </pre>
  );
}

function CostFooter() {
  const costs = useProjectStore((s) => s.costs);
  const totalIn = costs.reduce((a, c) => a + c.input_tokens, 0);
  const totalOut = costs.reduce((a, c) => a + c.output_tokens, 0);
  return (
    <footer
      data-testid="cost-footer"
      className="flex items-center justify-between rounded border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300"
    >
      <span>{costs.length} provider call(s)</span>
      <span>
        in {totalIn} · out {totalOut} tokens
      </span>
    </footer>
  );
}

export default function Studio() {
  const { id } = useParams();
  const navigate = useNavigate();
  useProjectSync(id);

  const view = useProjectStore((s) => s.view);
  const agentStream = useProjectStore((s) => s.agentStream);

  const state = view?.state ?? 'intake';
  const usedHighTemp = (view?.directions ?? []).some(
    (d) => d.brain === 'claude_high_temp'
  );

  // Route to the correct surface once the run leaves the live-theater states.
  useEffect(() => {
    if (!id || !view) return;
    const target = routeForState(view.state, id);
    if (target !== `/studio/${id}`) navigate(target);
  }, [id, view, navigate]);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6 text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Studio</h1>
        <RunStateChip state={state} />
      </div>

      <ModeBanner highTemp={usedHighTemp} />
      <PipelineSpine state={state} />

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-slate-300">Agent stream</h2>
          <AgentStream text={agentStream} />
        </div>

        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-slate-300">Directions</h2>
          <div data-testid="lane-grid" className="grid grid-cols-2 gap-2">
            {(view?.directions ?? []).length === 0 ? (
              <p className="col-span-2 text-xs text-slate-500">
                Directions will appear here as they are explored…
              </p>
            ) : (
              (view?.directions ?? []).map((d) => (
                <div
                  key={d.id}
                  data-testid="lane-card"
                  className="rounded border border-slate-800 bg-slate-900 p-2"
                >
                  <div className="mb-1 flex items-center gap-1">
                    <span className="truncate text-xs font-medium">
                      {d.territory.label || 'exploring…'}
                    </span>
                    <span className="ml-auto rounded bg-slate-800 px-1 text-[9px] text-slate-300">
                      {d.brain}
                    </span>
                  </div>
                  <div className="aspect-video rounded bg-slate-800" />
                  <p className="mt-1 truncate text-[11px] text-slate-400">
                    {d.big_idea || '…'}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <CostFooter />
    </main>
  );
}
