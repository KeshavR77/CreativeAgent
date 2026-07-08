/** RunStateChip — quiet mono state label with a status dot (pulsing when live). */
import type { RunState } from '../api/types';

// States where the machine is actively working (dot pulses).
const LIVE = new Set([
  'interrogating',
  'researching',
  'strategizing',
  'naming',
  'briefing',
  'seeding',
  'exploring',
  'diverging',
  'refining',
  'packaging',
]);

// States waiting on a human decision.
const GATED = new Set(['awaiting_strategy_approval', 'awaiting_curation']);

function toneFor(state: string): { dot: string; text: string } {
  if (GATED.has(state)) return { dot: 'bg-warn', text: 'text-warn' };
  if (LIVE.has(state)) return { dot: 'dot-live', text: 'text-accent' };
  if (state === 'done') return { dot: 'bg-ok', text: 'text-ok' };
  if (state === 'error' || state === 'cancelled') return { dot: 'bg-accent', text: 'text-accent' };
  return { dot: 'bg-faint', text: 'text-muted' };
}

export function RunStateChip({ state }: { state: RunState | string }) {
  const tone = toneFor(state);
  return (
    <span
      data-testid="run-state-chip"
      data-state={state}
      className={`inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-kicker ${tone.text}`}
    >
      <span className={`dot ${tone.dot}`} />
      {state.replace(/_/g, ' ')}
    </span>
  );
}
