/**
 * Export — the handoff surface. For each finalized ConceptPackage:
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
import { Shell } from '../components/Shell';
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
    <li className="flex flex-wrap items-center gap-3 border-b border-line py-1.5 font-mono text-[10px]">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 truncate text-faint">{img.url}</span>
      <span className="ml-auto">
        <ProvenanceTag image={img} />
      </span>
    </li>
  );
}

function PackageDoc({ pkg, projectId }: { pkg: ConceptPackage; projectId: string }) {
  return (
    <article className="panel flex flex-col gap-8 p-10">
      <header className="border-b border-line pb-6">
        <p className="kicker mb-2">Concept package</p>
        <h2 className="font-serif text-3xl text-ink">{pkg.territory_label}</h2>
        {pkg.names.length ? (
          <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted">
            {pkg.names.join(', ')}
            <span
              data-testid="unscreened-badge"
              className="rounded-sm bg-accent-soft px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-kicker text-accent"
            >
              unscreened
            </span>
          </p>
        ) : null}
      </header>

      <section>
        <h3 className="kicker mb-2">Strategy</h3>
        <p className="font-serif text-xl leading-snug text-ink">{pkg.strategy.positioning}</p>
        <p className="mt-2 text-[14px] italic text-muted">{pkg.strategy.key_message}</p>
      </section>

      <section>
        <h3 className="kicker mb-2">Big idea</h3>
        <p className="text-[15px] leading-relaxed text-ink-soft">{pkg.big_idea}</p>
      </section>

      {/* Sketches section — thumbnails + AI-generated note */}
      <section data-testid="package-sketches">
        <h3 className="kicker mb-1">Sketches</h3>
        <p className="mb-3 font-mono text-[10px] text-faint">
          Sketches are AI-generated (or placeholders when image-gen is unavailable).
        </p>
        <div className="grid grid-cols-3 gap-3">
          {pkg.sketches.map((s, i) => (
            <ImageTile key={`${s.url}-${i}`} image={s} />
          ))}
        </div>
      </section>

      {/* Moodboard — mixed provenance tags */}
      <section data-testid="package-moodboard">
        <h3 className="kicker mb-3">Moodboard</h3>
        <div className="grid grid-cols-4 gap-3">
          {pkg.art_direction.moodboard.map((m, i) => (
            <ImageTile key={`${m.url}-${i}`} image={m} />
          ))}
        </div>
      </section>

      <section>
        <h3 className="kicker mb-2">Copy</h3>
        <p className="font-serif text-2xl leading-snug text-ink">{pkg.copy.headline}</p>
        {pkg.copy.subhead ? (
          <p className="mt-2 text-[15px] text-ink-soft">{pkg.copy.subhead}</p>
        ) : null}
        {pkg.copy.cta ? (
          <p className="mt-2 font-mono text-[12px] uppercase tracking-kicker text-accent">
            → {pkg.copy.cta}
          </p>
        ) : null}
      </section>

      {/* TokenExport */}
      <section data-testid="token-export" className="flex flex-wrap gap-2 border-t border-line pt-6">
        <a href={api.exportMarkdownUrl(projectId, pkg.direction_id)} download className="btn-ghost">
          Download export.md
        </a>
        <a href={api.tokensJsonUrl(projectId, pkg.direction_id)} download className="btn-ghost">
          Download tokens.json
        </a>
        <a href={api.tokensCssUrl(projectId, pkg.direction_id)} download className="btn-ghost">
          Download tokens.css
        </a>
      </section>

      {/* AssetLicensePanel */}
      <section data-testid="asset-license-panel">
        <h3 className="kicker mb-2">Assets &amp; licensing</h3>
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
    <Shell surface="Export">
      <div className="flex flex-col gap-6">
        <h1 className="sr-only">Export</h1>

        {loaded && packages.length === 0 ? (
          <p className="text-sm text-muted">
            No finalized packages yet. Finalize a promoted direction in the Cockpit.
          </p>
        ) : null}

        {/* AiDisclosureNote */}
        {packages.length ? (
          <aside
            data-testid="ai-disclosure-note"
            className="rounded-sm border border-line bg-panel px-4 py-3 font-mono text-[11px] leading-relaxed text-muted"
          >
            <strong className="text-ink">AI disclosure.</strong> This export contains{' '}
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
      </div>
    </Shell>
  );
}
