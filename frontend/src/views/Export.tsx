/**
 * Export (§14.3) — the handoff surface. For each finalized ConceptPackage:
 *   - PackageDoc: strategy, big idea, a Sketches section (thumbnails + an
 *     "AI-generated" note), art direction, and the mixed-provenance moodboard
 *     (each tile keeps its provenance tag).
 *   - TokenExport: download links for tokens.json / tokens.css / export.md.
 *   - AssetLicensePanel: every image listed with its provenance/licence.
 *   - AiDisclosureNote: itemized generated-vs-sourced counts.
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ProvenanceTag } from '../components/ProvenanceTag';
import { ImageTile } from '../components/ImageTile';
import type { ConceptPackage, ImageRef } from '../api/types';

function countProvenance(packages: ConceptPackage[]) {
  let generated = 0;
  let sourced = 0;
  let placeholder = 0;
  for (const pkg of packages) {
    for (const img of [...pkg.sketches, ...pkg.art_direction.moodboard]) {
      if (img.kind === 'generated') generated += 1;
      else if (img.kind === 'sourced') sourced += 1;
      else placeholder += 1;
    }
  }
  return { generated, sourced, placeholder };
}

function AssetLine({ label, img }: { label: string; img: ImageRef }) {
  return (
    <li className="flex flex-wrap items-center gap-2 border-b border-slate-800 py-1 text-xs">
      <span className="font-mono text-slate-400">{label}</span>
      <span className="truncate text-slate-300">{img.url}</span>
      <span className="ml-auto">
        <ProvenanceTag image={img} />
      </span>
    </li>
  );
}

function PackageDoc({ pkg, projectId }: { pkg: ConceptPackage; projectId: string }) {
  return (
    <article className="flex flex-col gap-4 rounded-lg border border-slate-700 bg-slate-900 p-4">
      <header className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{pkg.territory_label}</h2>
        {pkg.names.length ? (
          <span className="flex items-center gap-1 text-xs text-slate-400">
            {pkg.names.join(', ')}
            <span
              data-testid="unscreened-badge"
              className="rounded bg-rose-900 px-1.5 py-0.5 text-[10px] text-rose-100"
            >
              unscreened
            </span>
          </span>
        ) : null}
      </header>

      <section>
        <h3 className="text-sm font-semibold text-slate-300">Strategy</h3>
        <p className="text-sm text-slate-200">{pkg.strategy.positioning}</p>
        <p className="text-xs italic text-slate-400">{pkg.strategy.key_message}</p>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-300">Big idea</h3>
        <p className="text-sm text-slate-200">{pkg.big_idea}</p>
      </section>

      {/* Sketches section — thumbnails + AI-generated note */}
      <section data-testid="package-sketches">
        <h3 className="text-sm font-semibold text-slate-300">Sketches</h3>
        <p className="mb-1 text-[10px] text-slate-500">
          Sketches are AI-generated (or placeholders when image-gen is unavailable).
        </p>
        <div className="grid grid-cols-3 gap-2">
          {pkg.sketches.map((s, i) => (
            <ImageTile key={`${s.url}-${i}`} image={s} />
          ))}
        </div>
      </section>

      {/* Moodboard — mixed provenance tags */}
      <section data-testid="package-moodboard">
        <h3 className="text-sm font-semibold text-slate-300">Moodboard</h3>
        <div className="grid grid-cols-4 gap-2">
          {pkg.art_direction.moodboard.map((m, i) => (
            <ImageTile key={`${m.url}-${i}`} image={m} />
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-300">Copy</h3>
        <p className="text-sm font-medium text-slate-100">{pkg.copy.headline}</p>
        {pkg.copy.subhead ? <p className="text-sm text-slate-300">{pkg.copy.subhead}</p> : null}
        {pkg.copy.cta ? <p className="text-sm text-sky-300">→ {pkg.copy.cta}</p> : null}
      </section>

      {/* TokenExport */}
      <section data-testid="token-export" className="flex flex-wrap gap-2">
        <a
          href={api.exportMarkdownUrl(projectId, pkg.direction_id)}
          download
          className="rounded bg-slate-700 px-2 py-1 text-xs"
        >
          Download export.md
        </a>
        <a
          href={api.tokensJsonUrl(projectId, pkg.direction_id)}
          download
          className="rounded bg-slate-700 px-2 py-1 text-xs"
        >
          Download tokens.json
        </a>
        <a
          href={api.tokensCssUrl(projectId, pkg.direction_id)}
          download
          className="rounded bg-slate-700 px-2 py-1 text-xs"
        >
          Download tokens.css
        </a>
      </section>

      {/* AssetLicensePanel */}
      <section data-testid="asset-license-panel">
        <h3 className="text-sm font-semibold text-slate-300">Assets &amp; licensing</h3>
        <ul>
          {pkg.sketches.map((s, i) => (
            <AssetLine key={`sk-${i}`} label="Sketch" img={s} />
          ))}
          {pkg.art_direction.moodboard.map((m, i) => (
            <AssetLine key={`mb-${i}`} label="Moodboard" img={m} />
          ))}
        </ul>
      </section>
    </article>
  );
}

export default function Export() {
  const { id } = useParams();
  const [packages, setPackages] = useState<ConceptPackage[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        setPackages(await api.packages(id));
      } catch {
        /* not finalized yet */
      } finally {
        setLoaded(true);
      }
    })();
  }, [id]);

  const counts = countProvenance(packages);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-4 p-6 text-slate-100">
      <h1 className="text-2xl font-bold">Export</h1>

      {loaded && packages.length === 0 ? (
        <p className="text-sm text-slate-400">
          No finalized packages yet. Finalize a promoted direction in the Cockpit.
        </p>
      ) : null}

      {/* AiDisclosureNote */}
      {packages.length ? (
        <aside
          data-testid="ai-disclosure-note"
          className="rounded border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300"
        >
          <strong>AI disclosure.</strong> This export contains{' '}
          {counts.generated} AI-generated image(s) and {counts.sourced} sourced
          image(s)
          {counts.placeholder ? ` (plus ${counts.placeholder} placeholder(s))` : ''}.
          Sketch and moodboard generation are AI-assisted and labeled per image.
          Candidate brand names are unscreened for trademark and must be cleared
          before use.
        </aside>
      ) : null}

      {id
        ? packages.map((pkg) => (
            <PackageDoc key={pkg.direction_id} pkg={pkg} projectId={id} />
          ))
        : null}
    </main>
  );
}
