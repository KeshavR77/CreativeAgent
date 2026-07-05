/**
 * ProvenanceTag — the mandatory attribution shown on EVERY image tile (§19 trap:
 * never surface an image without its provenance). Renders per-kind:
 *   generated:   "AI-generated · <gen_model>"   (prompt exposed on the tile hover)
 *   sourced:     "<provider> · <license> · © <attribution>"  (links source_url)
 *   placeholder: "placeholder — <caption>"
 */
import type { ImageRef } from '../api/types';

export function ProvenanceTag({ image }: { image: ImageRef }) {
  if (image.kind === 'generated') {
    return (
      <span
        data-testid="provenance-tag"
        data-kind="generated"
        className="text-[10px] leading-tight text-slate-300"
      >
        AI-generated · {image.gen_model}
      </span>
    );
  }

  if (image.kind === 'sourced') {
    return (
      <span
        data-testid="provenance-tag"
        data-kind="sourced"
        className="text-[10px] leading-tight text-slate-300"
      >
        {image.provider} · {image.license} · ©{' '}
        {image.source_url ? (
          <a
            href={image.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="underline"
          >
            {image.attribution}
          </a>
        ) : (
          image.attribution
        )}
      </span>
    );
  }

  // placeholder
  return (
    <span
      data-testid="provenance-tag"
      data-kind="placeholder"
      className="text-[10px] leading-tight text-amber-300"
    >
      placeholder{image.caption ? ` — ${image.caption}` : ''}
    </span>
  );
}
