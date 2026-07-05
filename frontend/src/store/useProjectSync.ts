/**
 * useProjectSync — binds a project id to the store: fetches /health (mode banner),
 * rehydrates the ProjectView (hard-refresh recovery), then opens a resilient SSE
 * stream. Each event is applied to the store; structural events trigger a full
 * view refetch so skeleton directions are replaced by real data (and the backend
 * remains the source of truth). SSE resume + this rehydrate = refresh recovery.
 */
import { useEffect } from 'react';
import { api } from '../api/client';
import { openEventStream } from '../api/sse';
import { useProjectStore } from './useProjectStore';
import type { SseEvent } from '../api/types';

const REFETCH_ON: ReadonlySet<string> = new Set([
  'run_state_changed',
  'direction_created',
  'direction_updated',
  'divergence_computed',
  'gate_reached',
  'gate_resolved',
  'artifact_written',
  'run_cancelled',
]);

export function useProjectSync(projectId: string | undefined) {
  useEffect(() => {
    if (!projectId) return;
    const store = useProjectStore.getState();
    let closed = false;
    let refetchTimer: ReturnType<typeof setTimeout> | null = null;

    const refetchView = () => {
      if (refetchTimer) return;
      refetchTimer = setTimeout(async () => {
        refetchTimer = null;
        try {
          const view = await api.getProject(projectId);
          if (!closed) useProjectStore.getState().setView(view);
        } catch {
          /* transient; the next event will retry */
        }
      }, 60);
    };

    // initial hydrate
    (async () => {
      try {
        const health = await api.health();
        if (!closed) useProjectStore.getState().setHealth(health);
      } catch {
        /* health optional */
      }
      try {
        const view = await api.getProject(projectId);
        if (!closed) useProjectStore.getState().setView(view);
      } catch {
        /* project may not exist yet */
      }
    })();

    const onEvent = (event: SseEvent) => {
      useProjectStore.getState().applyEvent(event);
      if (REFETCH_ON.has(event.type)) refetchView();
    };

    const conn = openEventStream(projectId, {
      onEvent,
      lastEventId: store.lastSeq,
    });

    return () => {
      closed = true;
      if (refetchTimer) clearTimeout(refetchTimer);
      conn.close();
    };
  }, [projectId]);
}
