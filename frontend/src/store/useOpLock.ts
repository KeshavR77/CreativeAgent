/**
 * useOpLock — a per-view single-flight lock. Curation ops must not overlap (the
 * backend serializes under a per-project lock and returns 409 for a wrong-state
 * call), so the UI disables actions while one is in flight. `run` wraps an async
 * op, flips `busy`, and swallows/reports errors so a rejected op still releases
 * the lock.
 */
import { useCallback, useRef, useState } from 'react';
import { ApiError } from '../api/client';

export function useOpLock() {
  const [busy, setBusy] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const run = useCallback(
    async <T>(op: () => Promise<T>): Promise<T | undefined> => {
      if (inFlight.current) return undefined; // drop overlapping clicks
      inFlight.current = true;
      setBusy(true);
      setLastError(null);
      try {
        return await op();
      } catch (err) {
        if (err instanceof ApiError) {
          setLastError(
            err.isConflict ? 'That action is not available right now.' : err.message
          );
        } else {
          setLastError((err as Error)?.message ?? 'Unexpected error');
        }
        return undefined;
      } finally {
        inFlight.current = false;
        setBusy(false);
      }
    },
    []
  );

  return { busy, lastError, run };
}
