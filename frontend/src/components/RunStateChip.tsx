/** A small colored chip for a project's RunState. */
import type { RunState } from '../api/types';

const TONE: Record<string, string> = {
  intake: 'bg-slate-700 text-slate-100',
  interrogating: 'bg-slate-700 text-slate-100',
  researching: 'bg-sky-800 text-sky-100',
  strategizing: 'bg-sky-800 text-sky-100',
  awaiting_strategy_approval: 'bg-amber-700 text-amber-50',
  naming: 'bg-sky-800 text-sky-100',
  briefing: 'bg-sky-800 text-sky-100',
  seeding: 'bg-indigo-800 text-indigo-100',
  exploring: 'bg-indigo-800 text-indigo-100',
  diverging: 'bg-indigo-800 text-indigo-100',
  awaiting_curation: 'bg-amber-700 text-amber-50',
  refining: 'bg-indigo-800 text-indigo-100',
  packaging: 'bg-emerald-800 text-emerald-100',
  done: 'bg-emerald-700 text-emerald-50',
  cancelled: 'bg-slate-600 text-slate-100',
  error: 'bg-rose-800 text-rose-50',
};

export function RunStateChip({ state }: { state: RunState | string }) {
  return (
    <span
      data-testid="run-state-chip"
      data-state={state}
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        TONE[state] ?? 'bg-slate-700 text-slate-100'
      }`}
    >
      {state}
    </span>
  );
}
