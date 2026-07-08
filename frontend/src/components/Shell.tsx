/**
 * Shell — shared app chrome: a hairline top bar with the wordmark, the current
 * surface name, and an optional right-side slot (usually the RunStateChip).
 * Pure presentation; no data fetching.
 */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface ShellProps {
  surface: string;
  right?: ReactNode;
  children: ReactNode;
  /** max-width class for the content column; default suits reading surfaces. */
  wide?: boolean;
}

export function Shell({ surface, right, children, wide }: ShellProps) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-paper/95 backdrop-blur-sm">
        <div className={`mx-auto flex h-12 items-center gap-4 px-6 ${wide ? 'max-w-6xl' : 'max-w-4xl'}`}>
          <Link to="/" className="font-mono text-[11px] font-semibold uppercase tracking-kicker text-ink hover:text-accent">
            Creative<span className="text-accent">/</span>Agent
          </Link>
          <span className="kicker mt-px">{surface}</span>
          <div className="ml-auto flex items-center gap-3">{right}</div>
        </div>
      </header>
      <main className={`mx-auto px-6 py-10 ${wide ? 'max-w-6xl' : 'max-w-4xl'}`}>{children}</main>
    </div>
  );
}
