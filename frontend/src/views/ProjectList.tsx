/**
 * ProjectList (§14.1) — create a project from a brief (+ optional brand K) and
 * list existing projects with their RunState chips. Creating a project also
 * starts it, then routes to the surface implied by the resulting RunState.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { routeForState } from '../store/useProjectStore';
import { RunStateChip } from '../components/RunStateChip';
import { Shell } from '../components/Shell';
import type { ProjectSummary } from '../api/types';

export default function ProjectList() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [brief, setBrief] = useState('');
  const [brand, setBrand] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      const { id } = await api.createProject({
        brief: brief.trim(),
        brand_name: brand.trim() || undefined,
      });
      // Kick off the run, then route by the resulting state.
      await api.startProject(id).catch(() => undefined);
      const view = await api.getProject(id);
      navigate(routeForState(view.state, id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Shell surface="Index">
      <h1 className="sr-only">Projects</h1>

      {/* Editorial masthead */}
      <div className="mb-12 border-b border-line pb-10">
        <p className="kicker mb-4">New brief</p>
        <form onSubmit={create} className="flex flex-col gap-4">
          <textarea
            id="brief"
            aria-label="Brief"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Describe the campaign or brand challenge…"
            rows={3}
            className="w-full resize-none border-0 bg-transparent font-serif text-2xl leading-snug text-ink placeholder:text-faint focus:outline-none"
          />
          <div className="flex items-center gap-3">
            <input
              aria-label="Brand name"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="Brand name (optional)"
              className="field max-w-xs"
            />
            <button
              type="submit"
              disabled={creating || !brief.trim()}
              className="btn-ink ml-auto"
            >
              {creating ? 'Creating…' : 'Create & start'}
            </button>
          </div>
          {error ? (
            <p className="font-mono text-[11px] text-accent" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </div>

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
