/**
 * SSE wrapper over the browser EventSource with:
 *   - Last-Event-ID resume (reconnect carries the highest applied seq so the
 *     backend backfills from there — see backend/app/api/routes_events.py),
 *   - exponential backoff between reconnect attempts,
 *   - seq-ordered delivery with a high-water mark so late/duplicate frames
 *     (re-delivered during backfill) are dropped rather than re-applied.
 *
 * The frontend never talks to any model/image/search provider — only this REST/SSE
 * surface (§2). All backend event types are addressed here as named SSE events.
 */
import type { EventType, SseEvent } from './types';

const EVENT_TYPES: EventType[] = [
  'run_created',
  'run_state_changed',
  'agent_started',
  'agent_completed',
  'agent_failed',
  'agent_token',
  'artifact_written',
  'direction_created',
  'direction_updated',
  'divergence_computed',
  'gate_reached',
  'gate_resolved',
  'cost_recorded',
  'run_cancelled',
];

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 15000;

export interface EventStreamOptions {
  onEvent: (event: SseEvent) => void;
  onOpen?: () => void;
  onError?: (err: Event) => void;
  /** resume cursor to start from (defaults to 0 = full backfill). */
  lastEventId?: number;
  /** base path; defaults to "/api". */
  base?: string;
}

export interface EventStreamHandle {
  close: () => void;
  /** the current resume cursor (highest applied seq), as a string. */
  lastEventId: () => string;
}

/**
 * Open a resilient SSE stream for a project. Returns a handle to close it and to
 * read the current resume cursor. Delivery is de-duplicated and ordered by seq.
 */
export function openEventStream(
  projectId: string,
  opts: EventStreamOptions
): EventStreamHandle {
  const base = opts.base ?? '/api';
  let highWater = opts.lastEventId ?? 0;
  let backoff = INITIAL_BACKOFF_MS;
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  const handleFrame = (type: string, msg: MessageEvent) => {
    const seq = Number(msg.lastEventId);
    if (!Number.isFinite(seq)) return;
    // Ordering + dedup: only advance on strictly-newer seqs. Backfill re-delivers
    // already-applied frames (<= highWater); those are dropped here.
    if (seq <= highWater) return;
    highWater = seq;
    // successful delivery resets the backoff window
    backoff = INITIAL_BACKOFF_MS;
    let data: Record<string, unknown> = {};
    try {
      data = msg.data ? JSON.parse(msg.data) : {};
    } catch {
      data = {};
    }
    opts.onEvent({ seq, type, data });
  };

  const connect = () => {
    if (stopped) return;
    const url = `${base}/projects/${encodeURIComponent(
      projectId
    )}/events?lastEventId=${highWater}`;
    const es = new EventSource(url, { withCredentials: false });
    source = es;

    es.onopen = () => {
      backoff = INITIAL_BACKOFF_MS;
      opts.onOpen?.();
    };
    es.onerror = (err) => {
      opts.onError?.(err);
      // The browser EventSource auto-reconnects, but it does not send our
      // Last-Event-ID header/cursor semantics the way we want; we take control:
      // close and reconnect ourselves with the current high-water mark.
      try {
        es.close();
      } catch {
        /* ignore */
      }
      if (stopped) return;
      scheduleReconnect();
    };

    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (ev) => handleFrame(type, ev as MessageEvent));
    }
    // Also handle the default (unnamed) message channel, just in case.
    es.onmessage = (ev) => handleFrame('message', ev);
  };

  const scheduleReconnect = () => {
    if (stopped || reconnectTimer) return;
    const delay = backoff;
    backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  };

  connect();

  return {
    close: () => {
      stopped = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (source) {
        try {
          source.close();
        } catch {
          /* ignore */
        }
        source = null;
      }
    },
    lastEventId: () => String(highWater),
  };
}
