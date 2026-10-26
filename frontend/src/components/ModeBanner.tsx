/**
 * ModeBanner — surfaces mock-mode transparency. Shown whenever any
 * provider is on the mock (from /health). The distinct claude_high_temp ideator
 * badge is rendered separately on directions/Studio, but the banner also notes it
 * when present so nothing about "this was mocked / high-temp" is hidden.
 */
import { useProjectStore } from '../store/useProjectStore';

export function ModeBanner({ highTemp }: { highTemp?: boolean }) {
  const mocked = useProjectStore((s) => s.mocked);
  const health = useProjectStore((s) => s.health);
  if (!mocked && !highTemp) return null;

  const mockedProviders = health
    ? Object.entries(health.providers)
        .filter(([, mode]) => mode !== 'real')
        .map(([name]) => name)
    : [];

  return (
    <div
      data-testid="mode-banner"
      role="status"
      className="flex flex-wrap items-center gap-2 rounded-sm border border-warn/40 bg-warnSoft px-3 py-2 font-mono text-[11px] text-warn"
    >
      {mocked ? (
        <span>
          Running in <strong>mocked mode</strong>
          {mockedProviders.length ? ` (${mockedProviders.join(', ')})` : ''} — outputs
          are illustrative, not live provider results.
        </span>
      ) : null}
      {highTemp ? (
        <span
          data-testid="high-temp-badge"
          className="rounded-sm border border-warn/40 px-1.5 py-0.5 text-[10px]"
        >
          ideator: claude_high_temp
        </span>
      ) : null}
    </div>
  );
}
