import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { openEventStream } from './sse';
import { useProjectStore } from '../store/useProjectStore';
import type { ProjectView, SseEvent } from './types';

// --------------------------------------------------------------------------- //
// A controllable EventSource mock (no live backend).                            //
// --------------------------------------------------------------------------- //
class MockEventSource {
  static instances: MockEventSource[] = [];
  static last(): MockEventSource {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }

  url: string;
  withCredentials: boolean;
  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  listeners: Record<string, ((ev: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = !!init?.withCredentials;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (ev: MessageEvent) => void) {
    (this.listeners[type] ||= []).push(cb);
  }
  removeEventListener(type: string, cb: (ev: MessageEvent) => void) {
    this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== cb);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }

  // ---- test drivers ----
  emit(type: string, data: unknown, lastEventId: string) {
    const msg = { data: JSON.stringify(data), lastEventId } as MessageEvent;
    (this.listeners[type] || []).forEach((cb) => cb(msg));
  }
  fail() {
    this.readyState = 2;
    this.onerror?.(new Event('error'));
  }
}

function makeView(overrides: Partial<ProjectView> = {}): ProjectView {
  return {
    id: 'p1',
    state: 'exploring',
    brief_excerpt: '',
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

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);
  vi.useFakeTimers();
  useProjectStore.getState().reset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('openEventStream ordering + dedup', () => {
  it('applies frames in seq order and ignores out-of-order stale frames', () => {
    const seen: SseEvent[] = [];
    const conn = openEventStream('p1', { onEvent: (e) => seen.push(e) });

    const es = MockEventSource.last();
    es.emit('run_state_changed', { to_state: 'researching' }, '1');
    es.emit('run_state_changed', { to_state: 'strategizing' }, '3');
    // stale replay (seq 2) arriving late must be dropped by the seq high-water mark.
    es.emit('run_state_changed', { to_state: 'intake' }, '2');

    expect(seen.map((e) => e.seq)).toEqual([1, 3]);
    conn.close();
  });

  it('parses each frame into {seq, type, data}', () => {
    const seen: SseEvent[] = [];
    const conn = openEventStream('p1', { onEvent: (e) => seen.push(e) });
    MockEventSource.last().emit('direction_created', { direction_id: 'd1', brain: 'mock' }, '7');
    expect(seen[0]).toEqual({
      seq: 7,
      type: 'direction_created',
      data: { direction_id: 'd1', brain: 'mock' },
    });
    conn.close();
  });
});

describe('backfill after a simulated disconnect (Last-Event-ID resume)', () => {
  it('reconnects with the last applied seq as Last-Event-ID and drops re-delivered frames', () => {
    useProjectStore.getState().setView(makeView());
    const applied: SseEvent[] = [];
    const conn = openEventStream('p1', {
      onEvent: (e) => {
        applied.push(e);
        useProjectStore.getState().applyEvent(e);
      },
    });

    // First connection delivers up to seq 3.
    const es1 = MockEventSource.last();
    es1.emit('direction_created', { direction_id: 'd1', brain: 'mock' }, '1');
    es1.emit('direction_created', { direction_id: 'd2', brain: 'mock' }, '2');
    es1.emit('run_state_changed', { to_state: 'diverging' }, '3');
    expect(useProjectStore.getState().lastSeq).toBe(3);

    // Simulate a disconnect; the wrapper should schedule a reconnect (backoff).
    es1.fail();
    expect(es1.closed).toBe(true);
    vi.advanceTimersByTime(5000);

    // A NEW EventSource is created for the resume, carrying the resume cursor.
    const es2 = MockEventSource.last();
    expect(es2).not.toBe(es1);
    expect(conn.lastEventId()).toBe('3'); // resume cursor == high-water mark
    expect(es2.url).toContain('lastEventId=3');

    // Backfill re-delivers seq 3 (already applied) + a fresh seq 4.
    es2.emit('run_state_changed', { to_state: 'diverging' }, '3'); // dup
    es2.emit('direction_created', { direction_id: 'd3', brain: 'mock' }, '4'); // new

    // The duplicate is dropped; only the new one advances state.
    expect(useProjectStore.getState().view!.directions.map((d) => d.id)).toEqual([
      'd1',
      'd2',
      'd3',
    ]);
    expect(useProjectStore.getState().lastSeq).toBe(4);
    conn.close();
  });

  it('uses exponential backoff across repeated failures', () => {
    const conn = openEventStream('p1', { onEvent: () => {} });
    const first = MockEventSource.last();

    first.fail();
    // No reconnect before the first backoff window elapses.
    vi.advanceTimersByTime(400);
    expect(MockEventSource.instances).toHaveLength(1);
    // After the initial delay, a reconnect happens.
    vi.advanceTimersByTime(600);
    expect(MockEventSource.instances).toHaveLength(2);

    MockEventSource.last().fail();
    // Second backoff is longer than the first; still only 2 after a short wait.
    vi.advanceTimersByTime(600);
    expect(MockEventSource.instances).toHaveLength(2);
    vi.advanceTimersByTime(2000);
    expect(MockEventSource.instances).toHaveLength(3);
    conn.close();
  });

  it('close() stops further reconnects', () => {
    const conn = openEventStream('p1', { onEvent: () => {} });
    const es = MockEventSource.last();
    conn.close();
    es.fail();
    vi.advanceTimersByTime(10000);
    expect(MockEventSource.instances).toHaveLength(1);
  });
});
