import { describe, it, expect, beforeEach } from 'vitest';
import { useProjectStore, routeForState } from './useProjectStore';
import type {
  ProjectView,
  Direction,
  SseEvent,
  HealthSnapshot,
} from '../api/types';

// --------------------------------------------------------------------------- //
// fixtures                                                                      //
// --------------------------------------------------------------------------- //
function makeView(overrides: Partial<ProjectView> = {}): ProjectView {
  return {
    id: 'p1',
    state: 'intake',
    brief_excerpt: 'a brief',
    error: null,
    created_at: null,
    updated_at: null,
    brief: null,
    strategy: null,
    verbal_identity: null,
    creative_brief: null,
    territories: [],
    directions: [],
    divergence: null,
    packages: [],
    interrupt: null,
    ...overrides,
  };
}

function makeDirection(id: string, overrides: Partial<Direction> = {}): Direction {
  return {
    id,
    territory: { label: 'T', lens: 'lens', description: '' },
    big_idea: 'idea ' + id,
    brain: 'mock',
    art_direction: {
      mood_descriptors: [],
      imagery_direction: 'imagery',
      layout_notes: '',
      palette: [],
      typography: [],
      moodboard: [],
    },
    copy: { headline: 'head', subhead: '', body: '', taglines: [], cta: '' },
    sketches: [],
    critique: null,
    critique_stale: false,
    divergence_score: null,
    status: 'draft',
    annotations: [],
    parent_id: null,
    merged_from: [],
    lens_tweak: null,
    ...overrides,
  };
}

function ev(seq: number, type: string, data: Record<string, unknown>): SseEvent {
  return { seq, type, data };
}

beforeEach(() => {
  useProjectStore.getState().reset();
});

// --------------------------------------------------------------------------- //
// RunState -> view routing                                                      //
// --------------------------------------------------------------------------- //
describe('routeForState (RunState -> view routing)', () => {
  it('routes pre-strategy states to the Studio surface', () => {
    for (const s of [
      'intake',
      'interrogating',
      'researching',
      'strategizing',
      'naming',
      'briefing',
      'seeding',
      'exploring',
      'diverging',
    ] as const) {
      expect(routeForState(s, 'p1')).toBe('/studio/p1');
    }
  });

  it('routes the two gate states to the Cockpit surface', () => {
    expect(routeForState('awaiting_strategy_approval', 'p1')).toBe('/cockpit/p1');
    expect(routeForState('awaiting_curation', 'p1')).toBe('/cockpit/p1');
  });

  it('routes terminal done -> Export', () => {
    expect(routeForState('done', 'p1')).toBe('/export/p1');
  });
});

// --------------------------------------------------------------------------- //
// SSE event reducer — one assertion per event type                              //
// --------------------------------------------------------------------------- //
describe('applyEvent reducer (per event type)', () => {
  it('run_state_changed updates view.state from to_state', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ state: 'intake' }));
    st.applyEvent(ev(1, 'run_state_changed', { from_state: 'intake', to_state: 'researching' }));
    expect(useProjectStore.getState().view?.state).toBe('researching');
  });

  it('direction_created appends a skeleton direction carrying its brain', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ state: 'exploring' }));
    st.applyEvent(ev(2, 'direction_created', { direction_id: 'd1', brain: 'claude_high_temp' }));
    const dirs = useProjectStore.getState().view!.directions;
    expect(dirs).toHaveLength(1);
    expect(dirs[0].id).toBe('d1');
    expect(dirs[0].brain).toBe('claude_high_temp');
  });

  it('direction_created is idempotent by id (upsert, not duplicate)', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ directions: [makeDirection('d1')] }));
    st.applyEvent(ev(3, 'direction_created', { direction_id: 'd1', brain: 'mock' }));
    expect(useProjectStore.getState().view!.directions).toHaveLength(1);
  });

  it('direction_updated is signal-only: advances lastSeq, leaves the view intact (refetch re-syncs)', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ directions: [makeDirection('d1')] }));
    const before = useProjectStore.getState().view!.directions[0];
    st.applyEvent(ev(4, 'direction_updated', { direction_id: 'd1', change: 'edit' }));
    expect(useProjectStore.getState().view!.directions[0]).toEqual(before);
    expect(useProjectStore.getState().lastSeq).toBe(4);
  });

  it('divergence_computed stores the {min, mean, warning} report', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    st.applyEvent(ev(5, 'divergence_computed', { min: 0.1, mean: 0.5, warning: true }));
    expect(useProjectStore.getState().view!.divergence).toEqual({
      min: 0.1,
      mean: 0.5,
      warning: true,
    });
  });

  it('gate_reached stores the interrupt payload', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    const payload = { gate: 'strategy', strategy: null };
    st.applyEvent(ev(6, 'gate_reached', { gate: 'strategy', payload }));
    expect(useProjectStore.getState().view!.interrupt).toEqual(payload);
  });

  it('gate_resolved clears the interrupt payload', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ interrupt: { gate: 'strategy' } }));
    st.applyEvent(ev(7, 'gate_resolved', { gate: 'strategy' }));
    expect(useProjectStore.getState().view!.interrupt).toBeNull();
  });

  it('cost_recorded accumulates into the cost list', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    st.applyEvent(ev(8, 'cost_recorded', { agent: 'ideator', model: 'mock', input_tokens: 10, output_tokens: 2 }));
    st.applyEvent(ev(9, 'cost_recorded', { agent: 'critic', model: 'mock', input_tokens: 5, output_tokens: 1 }));
    expect(useProjectStore.getState().costs).toHaveLength(2);
    expect(useProjectStore.getState().costs[0].agent).toBe('ideator');
  });

  it('agent_token appends batched tokens to the agent stream buffer', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    st.applyEvent(ev(10, 'agent_started', { agent: 'ideator' }));
    st.applyEvent(ev(11, 'agent_token', { agent: 'ideator', token: 'Hello ' }));
    st.applyEvent(ev(12, 'agent_token', { agent: 'ideator', token: 'world' }));
    expect(useProjectStore.getState().agentStream).toContain('Hello world');
  });

  it('run_cancelled flips view.state to cancelled', () => {
    const st = useProjectStore.getState();
    st.setView(makeView({ state: 'exploring' }));
    st.applyEvent(ev(13, 'run_cancelled', {}));
    expect(useProjectStore.getState().view!.state).toBe('cancelled');
  });

  it('tracks the highest applied seq (SSE resume high-water mark)', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    st.applyEvent(ev(4, 'run_state_changed', { to_state: 'researching' }));
    st.applyEvent(ev(7, 'run_state_changed', { to_state: 'strategizing' }));
    expect(useProjectStore.getState().lastSeq).toBe(7);
  });

  it('ignores already-applied (<= lastSeq) events so replays never double-count', () => {
    const st = useProjectStore.getState();
    st.setView(makeView());
    st.applyEvent(ev(8, 'cost_recorded', { agent: 'ideator', model: 'mock', input_tokens: 10, output_tokens: 2 }));
    // a re-delivered frame at the same seq, and an older one, must both be dropped
    st.applyEvent(ev(8, 'cost_recorded', { agent: 'ideator', model: 'mock', input_tokens: 10, output_tokens: 2 }));
    st.applyEvent(ev(3, 'cost_recorded', { agent: 'old', model: 'mock', input_tokens: 1, output_tokens: 1 }));
    expect(useProjectStore.getState().costs).toHaveLength(1);
  });
});

// --------------------------------------------------------------------------- //
// mode-banner state from /health                                                //
// --------------------------------------------------------------------------- //
describe('mode-banner state from /health', () => {
  function health(overrides: Partial<HealthSnapshot> = {}): HealthSnapshot {
    return {
      status: 'ok',
      providers: { claude: 'mock', conceptial: 'mock', search: 'mock', embeddings: 'mock' },
      image_gen: { enabled: false, provider: null },
      image_source: { enabled: false, provider: null },
      tracing: false,
      ...overrides,
    };
  }

  it('flags mocked mode when any provider is on the mock', () => {
    useProjectStore.getState().setHealth(health());
    expect(useProjectStore.getState().mocked).toBe(true);
  });

  it('clears mocked mode when every provider is real (backend value contract)', () => {
    // Regression: the backend health snapshot reports "real"/"mock", never "live".
    // A 'live' fixture would pass while the real banner stayed stuck on "MOCKED".
    useProjectStore.getState().setHealth(
      health({ providers: { claude: 'real', conceptial: 'real', search: 'real', embeddings: 'real' } })
    );
    expect(useProjectStore.getState().mocked).toBe(false);
  });
});
