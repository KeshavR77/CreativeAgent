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
        className="font-mono text-[9px] leading-tight text-muted"
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
        className="font-mono text-[9px] leading-tight text-muted"
      >
        {image.provider} · {image.license} · ©{' '}
        {image.source_url ? (
          <a
            href={image.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="underline decoration-line underline-offset-2 hover:text-accent"
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
      className="font-mono text-[9px] leading-tight text-warn"
    >
      placeholder{image.caption ? ` — ${image.caption}` : ''}
    </span>
  );
}
