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
    <main className="mx-auto max-w-3xl p-6 text-slate-100">
      <h1 className="mb-4 text-2xl font-bold">Projects</h1>

      <form
        onSubmit={create}
        className="mb-6 flex flex-col gap-2 rounded-lg border border-slate-700 bg-slate-900 p-4"
      >
        <label className="text-sm font-medium" htmlFor="brief">
          New brief
        </label>
        <textarea
          id="brief"
          aria-label="Brief"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Describe the campaign or brand challenge…"
          rows={3}
          className="w-full rounded bg-slate-950 p-2 text-sm"
        />
        <input
          aria-label="Brand name"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          placeholder="Brand name (optional)"
          className="w-full rounded bg-slate-950 p-2 text-sm"
        />
        {error ? <p className="text-xs text-rose-400">{error}</p> : null}
        <button
          type="submit"
          disabled={creating || !brief.trim()}
          className="self-start rounded bg-sky-700 px-3 py-1.5 text-sm font-medium disabled:opacity-40"
        >
          {creating ? 'Creating…' : 'Create & start'}
        </button>
      </form>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
          History
        </h2>
        {projects.length === 0 ? (
          <p className="text-sm text-slate-500">No projects yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => navigate(routeForState(p.state, p.id))}
                  className="flex w-full items-center justify-between gap-3 rounded border border-slate-800 bg-slate-900 p-3 text-left hover:border-slate-600"
                >
                  <span className="truncate text-sm">{p.brief_excerpt || p.id}</span>
                  <RunStateChip state={p.state} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
