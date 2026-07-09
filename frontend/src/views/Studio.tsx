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
import { Shell } from '../components/Shell';
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
  { key: 'awaiting_ideation', label: 'Ideation' },
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
    <ol data-testid="pipeline-spine" className="flex flex-wrap gap-x-5 gap-y-2 border-b border-line pb-5">
      {PIPELINE.map((node, i) => {
        const done = activeIndex > i;
        const active = activeIndex === i;
        return (
          <li
            key={node.key}
            data-active={active}
            data-done={done}
            className={`flex items-baseline gap-1.5 font-mono text-[10px] uppercase tracking-kicker ${
              active ? 'text-accent' : done ? 'text-ink' : 'text-faint'
            }`}
          >
            <span className="text-[9px]">{String(i + 1).padStart(2, '0')}</span>
            {node.label}
            {active ? <span className="dot dot-live ml-0.5" /> : null}
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
      className="max-h-72 overflow-auto whitespace-pre-wrap border-l-2 border-line pl-4 font-mono text-[11px] leading-relaxed text-ink-soft"
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
      className="flex items-center justify-between border-t border-line pt-3 font-mono text-[10px] uppercase tracking-kicker text-muted"
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
    <Shell surface="Studio" right={<RunStateChip state={state} />}>
      <div className="flex flex-col gap-8">
        <ModeBanner highTemp={usedHighTemp} />
        <PipelineSpine state={state} />

        <section className="grid grid-cols-1 gap-10 md:grid-cols-2">
          <div className="flex flex-col gap-3">
            <h2 className="kicker">Agent stream</h2>
            <AgentStream text={agentStream} />
          </div>

          <div className="flex flex-col gap-3">
            <h2 className="kicker">Directions</h2>
            <div data-testid="lane-grid" className="grid grid-cols-2 gap-3">
              {(view?.directions ?? []).length === 0 && (view?.territories ?? []).length > 0 ? (
                // Territories are seeded before branches land: show one skeleton
                // lane per territory so the fan-out is visible while it works.
                (view?.territories ?? []).map((t, ti) => (
                  <div key={`${t.label}-${ti}`} data-testid="lane-skeleton" className="panel flex flex-col gap-2 p-3">
                    <div className="flex items-baseline gap-2">
                      <span className="truncate font-serif text-[15px] text-ink">{t.label}</span>
                      <span className="dot dot-live ml-auto shrink-0" />
                    </div>
                    <div className="aspect-video animate-pulse rounded-sm bg-paper" />
                    <p className="truncate text-[12px] text-muted">{t.lens || 'exploring…'}</p>
                  </div>
                ))
              ) : (view?.directions ?? []).length === 0 ? (
                <p className="col-span-2 text-[13px] text-muted">
                  Directions will appear here as they are explored…
                </p>
              ) : (
                (view?.directions ?? []).map((d) => (
                  <div
                    key={d.id}
                    data-testid="lane-card"
                    className="panel flex flex-col gap-2 p-3"
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="truncate font-serif text-[15px] text-ink">
                        {d.territory.label || 'exploring…'}
                      </span>
                      <span className="ml-auto shrink-0 font-mono text-[9px] uppercase tracking-kicker text-muted">
                        {d.brain}
                      </span>
                    </div>
                    {d.sketches?.[0] ? (
                      <img
                        src={d.sketches[0].url}
                        alt=""
                        className="aspect-video w-full rounded-sm border border-line object-cover"
                      />
                    ) : (
                      <div className="aspect-video rounded-sm bg-paper" />
                    )}
                    <p className="truncate text-[12px] text-muted">{d.big_idea || '…'}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <CostFooter />
      </div>
    </Shell>
  );
}
