/**
 * Project store (zustand): holds the composed ProjectView, applies each SSE event
 * to it via a reducer, tracks the batched agent-token stream and the accumulated
 * cost list, and derives the mode banner ("mocked") from /health.
 *
 * RunState-driven routing lives in `routeForState`: Studio for the live-theater
 * states, Cockpit for the two human gates, Export once done.
 */
import { create } from 'zustand';
import type {
  ProjectView,
  Direction,
  DirectionChange,
  DivergenceReport,
  CostRecord,
  HealthSnapshot,
  RunState,
  SseEvent,
  Brain,
  InterruptPayload,
} from '../api/types';

/** A direction as held in the store: the model plus a transient last-change tag. */
export type StoredDirection = Direction & { lastChange?: DirectionChange | string };

/** A freshly-announced (direction_created) skeleton before the full view refetch. */
function skeletonDirection(id: string, brain: Brain | string): StoredDirection {
  return {
    id,
    territory: { label: '', lens: '', description: '' },
    big_idea: '',
    brain: (brain as Brain) ?? 'mock',
    art_direction: {
      mood_descriptors: [],
      imagery_direction: '',
      layout_notes: '',
      palette: [],
      typography: [],
      moodboard: [],
    },
    copy: { headline: '', subhead: '', body: '', taglines: [], cta: '' },
    sketches: [],
    critique: null,
    critique_stale: false,
    divergence_score: null,
    status: 'draft',
    annotations: [],
    parent_id: null,
    merged_from: [],
    lens_tweak: null,
  };
}

interface ProjectState {
  view: (ProjectView & { directions: StoredDirection[] }) | null;
  costs: CostRecord[];
  agentStream: string;
  lastSeq: number;
  health: HealthSnapshot | null;
  mocked: boolean;
  imageGenMocked: boolean;

  setView: (view: ProjectView) => void;
  setHealth: (health: HealthSnapshot) => void;
  applyEvent: (event: SseEvent) => void;
  reset: () => void;
}

const INITIAL: Omit<
  ProjectState,
  'setView' | 'setHealth' | 'applyEvent' | 'reset'
> = {
  view: null,
  costs: [],
  agentStream: '',
  lastSeq: 0,
  health: null,
  mocked: false,
  imageGenMocked: false,
};

/** Upsert a direction into the list by id (mirrors the backend reducer). */
function upsertDirection(
  list: StoredDirection[],
  next: StoredDirection
): StoredDirection[] {
  const i = list.findIndex((d) => d.id === next.id);
  if (i === -1) return [...list, next];
  const merged = [...list];
  merged[i] = { ...merged[i], ...next };
  return merged;
}

export const useProjectStore = create<ProjectState>((set) => ({
  ...INITIAL,

  setView: (view) =>
    set({ view: view as ProjectView & { directions: StoredDirection[] } }),

  setHealth: (health) => {
    const p = health.providers;
    // The backend reports each provider as "real" or "mock" (backend/app/config.py
    // health_snapshot). "mocked" == the REASONING engine is on the mock: chat is
    // what makes outputs real or illustrative. Conceptial/search/embeddings are
    // optional lanes with truthful per-artifact fallbacks (brain labels,
    // provenance tags), so they don't flip the whole-run banner.
    const mocked = p.claude !== 'real';
    // image-gen "mocked" == not enabled with a real provider
    const imageGenMocked = !health.image_gen.enabled;
    set({ health, mocked, imageGenMocked });
  },

  applyEvent: (event) =>
    set((state) => {
      // Ignore already-applied events so a replayed/older frame can never
      // double-count the additive reducers (costs, agentStream). sse.ts also
      // dedupes by high-water mark; this is the authoritative backstop.
      if (event.seq <= state.lastSeq) return {};
      const patch: Partial<ProjectState> = { lastSeq: event.seq };

      const view = state.view;
      const data = event.data as Record<string, unknown>;

      switch (event.type) {
        case 'run_state_changed': {
          if (view && typeof data.to_state === 'string') {
            patch.view = { ...view, state: data.to_state as string };
          }
          break;
        }
        case 'run_cancelled': {
          if (view) patch.view = { ...view, state: 'cancelled' };
          break;
        }
        case 'direction_created': {
          if (view && typeof data.direction_id === 'string') {
            const dir = skeletonDirection(
              data.direction_id,
              (data.brain as string) ?? 'mock'
            );
            patch.view = {
              ...view,
              directions: upsertDirection(view.directions, dir),
            };
          }
          break;
        }
        case 'direction_updated': {
          if (view && typeof data.direction_id === 'string') {
            const directions: StoredDirection[] = view.directions.map(
              (d: StoredDirection) =>
                d.id === data.direction_id
                  ? { ...d, lastChange: (data.change as string) ?? d.lastChange }
                  : d
            );
            patch.view = { ...view, directions };
          }
          break;
        }
        case 'divergence_computed': {
          if (view) {
            const report: DivergenceReport = {
              min: (data.min as number) ?? null,
              mean: (data.mean as number) ?? null,
              warning: Boolean(data.warning),
            };
            patch.view = { ...view, divergence: report };
          }
          break;
        }
        case 'gate_reached': {
          if (view) {
            const payload = (data.payload as InterruptPayload) ?? {
              gate: data.gate as string,
            };
            patch.view = { ...view, interrupt: payload };
          }
          break;
        }
        case 'gate_resolved': {
          if (view) patch.view = { ...view, interrupt: null };
          break;
        }
        case 'cost_recorded': {
          const rec: CostRecord = {
            agent: (data.agent as string) ?? '',
            model: (data.model as string) ?? '',
            input_tokens: (data.input_tokens as number) ?? 0,
            output_tokens: (data.output_tokens as number) ?? 0,
          };
          patch.costs = [...state.costs, rec];
          break;
        }
        case 'agent_started': {
          // Narrate the run: one line per agent lifecycle event. (Token-level
          // streaming lands on 'agent_token' below when the backend emits it.)
          const territory = data.territory ? ` — ${data.territory as string}` : '';
          const line = `▸ ${(data.agent as string) ?? 'agent'}${territory}`;
          patch.agentStream = state.agentStream
            ? `${state.agentStream}\n${line}`
            : line;
          break;
        }
        case 'agent_completed': {
          const line = `  ✓ ${(data.agent as string) ?? 'agent'} complete`;
          patch.agentStream = state.agentStream
            ? `${state.agentStream}\n${line}`
            : line;
          break;
        }
        case 'agent_failed': {
          const line = `  ✗ ${(data.agent as string) ?? 'agent'} failed${
            data.territory ? ` — ${data.territory as string}` : ''
          }`;
          patch.agentStream = state.agentStream
            ? `${state.agentStream}\n${line}`
            : line;
          break;
        }
        case 'artifact_written': {
          const line = `  · ${(data.artifact as string) ?? 'artifact'} written`;
          patch.agentStream = state.agentStream
            ? `${state.agentStream}\n${line}`
            : line;
          break;
        }
        case 'agent_token': {
          const tok = (data.token as string) ?? (data.text as string) ?? '';
          patch.agentStream = state.agentStream + tok;
          break;
        }
        default:
          break;
      }
      return patch;
    }),

  reset: () => set({ ...INITIAL }),
}));

// --------------------------------------------------------------------------- //
// RunState -> route mapping                                                     //
// --------------------------------------------------------------------------- //
const COCKPIT_STATES: ReadonlySet<RunState> = new Set<RunState>([
  'awaiting_strategy_approval',
  'awaiting_curation',
]);

const EXPORT_STATES: ReadonlySet<RunState> = new Set<RunState>(['done']);

/**
 * Which surface a project's RunState should route to:
 *   gates  -> Cockpit, done -> Export, everything else -> Studio (live theater).
 */
export function routeForState(state: RunState | string, projectId: string): string {
  if (COCKPIT_STATES.has(state as RunState)) return `/cockpit/${projectId}`;
  if (EXPORT_STATES.has(state as RunState)) return `/export/${projectId}`;
  return `/studio/${projectId}`;
}
