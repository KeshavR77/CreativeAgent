/**
 * ImageTile — one image with its mandatory ProvenanceTag, an optional per-tile
 * regenerate (⟳) control, and optional extra controls (e.g. a SourceToggle).
 * The generated prompt is surfaced on hover via the `title` attribute.
 */
import type { ReactNode } from 'react';
import type { ImageRef } from '../api/types';
import { ProvenanceTag } from './ProvenanceTag';

interface ImageTileProps {
  image: ImageRef;
  /** per-tile regenerate handler; when omitted no ⟳ button is shown. */
  onRegenerate?: () => void;
  busy?: boolean;
  /** extra controls rendered under the provenance tag (e.g. SourceToggle). */
  controls?: ReactNode;
}

function hoverTitle(image: ImageRef): string | undefined {
  if (image.kind === 'generated' && image.gen_prompt) return image.gen_prompt;
  if (image.kind === 'sourced' && image.source_url) return image.source_url;
  if (image.caption) return image.caption;
  return undefined;
}

export function ImageTile({ image, onRegenerate, busy, controls }: ImageTileProps) {
  return (
    <figure
      data-testid="image-tile"
      data-kind={image.kind}
      title={hoverTitle(image)}
      className="relative flex flex-col gap-1 rounded-md border border-slate-700 bg-slate-900 p-1"
    >
      <div className="relative aspect-square w-full overflow-hidden rounded bg-slate-800">
        <img
          src={image.url}
          alt={image.caption ?? image.gen_prompt ?? 'concept image'}
          className="h-full w-full object-cover"
        />
        {onRegenerate ? (
          <button
            type="button"
            aria-label="Regenerate this image"
            title="Regenerate"
            disabled={busy}
            onClick={onRegenerate}
            className="absolute right-1 top-1 rounded bg-slate-950/80 px-1.5 py-0.5 text-xs text-slate-100 disabled:opacity-40"
          >
            ⟳
          </button>
        ) : null}
      </div>
      <figcaption className="flex flex-col gap-1">
        <ProvenanceTag image={image} />
        {controls}
      </figcaption>
    </figure>
  );
}
