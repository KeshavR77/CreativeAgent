/**
 * ProjectList — the entry point. The normal flow is to drop a client RFP
 * PDF: the backend distills it into a brief and seeds a project. A plain-text brief
 * is offered as a secondary path. Either way the project is created + started, then
 * routed to the surface implied by the resulting RunState.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { routeForState } from '../store/useProjectStore';
import { RunStateChip } from '../components/RunStateChip';
import { Shell } from '../components/Shell';
import type { IdeationMode, ProjectSummary } from '../api/types';

// How ideas get brainstormed for this engagement (backend ideation_mode).
const MODES: { value: IdeationMode; label: string; blurb: string }[] = [
  {
    value: 'internal',
    label: 'In-house',
    blurb: 'The model ideates end-to-end — fastest path.',
  },
  {
    value: 'manual',
    label: 'External studio',
    blurb: 'Pause for a downloadable packet; brainstorm with any tool, paste ideas back for critique.',
  },
  {
    value: 'auto',
    label: 'Auto loop',
    blurb: 'Brainstorm ⇄ critique rounds, automatically (uses the external ideator when configured).',
  },
];

export default function ProjectList() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [brief, setBrief] = useState('');
  const [brand, setBrand] = useState('');
  const [mode, setMode] = useState<IdeationMode>('internal');
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState('');
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    try {
      setProjects(await api.listProjects());
    } catch {
      /* backend may be down in dev; leave list empty */
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  // Shared: start a freshly-created project and route by its resulting state.
  const launch = async (id: string) => {
    await api.startProject(id).catch(() => undefined);
    const view = await api.getProject(id);
    navigate(routeForState(view.state, id));
  };

  const createFromText = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim() || busy) return;
    setBusy(true);
    setBusyLabel('Creating…');
    setError(null);
    try {
      const { id } = await api.createProject({
        brief: brief.trim(),
        brand_name: brand.trim() || undefined,
        ideation_mode: mode,
      });
      await launch(id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create project');
      setBusy(false);
    }
  };

  const createFromPdf = async (file: File) => {
    if (busy) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please drop a PDF file.');
      return;
    }
    setBusy(true);
    setBusyLabel('Reading the RFP…');
    setError(null);
    try {
      const { id } = await api.createProjectFromPdf(file, mode);
      setBusyLabel('Brief understood — starting…');
      await launch(id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not read that PDF');
      setBusy(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) createFromPdf(file);
  };

  return (
    <Shell surface="Index">
      <h1 className="sr-only">Projects</h1>

      {/* Primary entry: drop an RFP PDF */}
      <div className="mb-8">
        <p className="kicker mb-3">New engagement</p>

        {/* Ideation mode — how ideas get brainstormed for this engagement */}
        <div role="radiogroup" aria-label="Ideation mode" className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {MODES.map((m) => {
            const selected = mode === m.value;
            return (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={selected}
                disabled={busy}
                onClick={() => setMode(m.value)}
                className={`flex flex-col gap-1 rounded-sm border p-3 text-left transition-colors ${
                  selected ? 'border-ink bg-panel' : 'border-line bg-transparent hover:border-faint'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className={`dot ${selected ? 'bg-accent' : 'bg-faint'}`} />
                  <span className="font-mono text-[10px] uppercase tracking-kicker text-ink">
                    {m.label}
                  </span>
                </span>
                <span className="text-[12px] leading-snug text-muted">{m.blurb}</span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex w-full flex-col items-center justify-center gap-3 rounded-sm border border-dashed px-6 py-14 text-center transition-colors ${
            dragging ? 'border-accent bg-accent-soft' : 'border-line bg-panel hover:border-ink'
          } disabled:opacity-60`}
        >
          {busy ? (
            <>
              <span className="dot dot-live" />
              <span className="font-mono text-[12px] uppercase tracking-kicker text-accent">
                {busyLabel}
              </span>
            </>
          ) : (
            <>
              <span className="font-serif text-2xl text-ink">Drop the client RFP</span>
              <span className="font-mono text-[11px] uppercase tracking-kicker text-muted">
                PDF — we read it and draft the brief
              </span>
            </>
          )}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Upload RFP PDF"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) createFromPdf(file);
            e.target.value = '';
          }}
        />
      </div>

      {/* Secondary: a plain-text brief */}
      <details className="mb-12 border-b border-line pb-10">
        <summary className="kicker cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          or type a brief instead ▸
        </summary>
        <form onSubmit={createFromText} className="mt-4 flex flex-col gap-4">
          <textarea
            id="brief"
            aria-label="Brief"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Describe the campaign or brand challenge…"
            rows={3}
            className="w-full resize-none border-0 bg-transparent font-serif text-xl leading-snug text-ink placeholder:text-faint focus:outline-none"
          />
          <div className="flex items-center gap-3">
            <input
              aria-label="Brand name"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="Brand name (optional)"
              className="field max-w-xs"
            />
            <button type="submit" disabled={busy || !brief.trim()} className="btn-ink ml-auto">
              Create & start
            </button>
          </div>
        </form>
      </details>

      {error ? (
        <p className="mb-6 font-mono text-[11px] text-accent" role="alert">
          {error}
        </p>
      ) : null}

      {/* Ledger of past work */}
      <section>
        <h2 className="kicker mb-4">History</h2>
        {projects.length === 0 ? (
          <p className="text-sm text-muted">No projects yet.</p>
        ) : (
          <ul className="flex flex-col">
            {projects.map((p, i) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => navigate(routeForState(p.state, p.id))}
                  className="group flex w-full items-baseline gap-4 border-b border-line py-3.5 text-left transition-colors hover:bg-panel"
                >
                  <span className="font-mono text-[10px] text-faint">
                    {String(projects.length - i).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[15px] text-ink group-hover:text-accent">
                    {p.brief_excerpt || p.id}
                  </span>
                  <RunStateChip state={p.state} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Shell>
  );
}
