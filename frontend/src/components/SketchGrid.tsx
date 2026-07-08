/**
 * SketchGrid — 3–6 AI-generated (or placeholder) sketch tiles. Every tile shows
 * its ProvenanceTag ("AI-generated · <model>", prompt on hover). Per-tile ⟳ maps
 * to /regenerate_sketch{index}; "Regenerate all sketches" maps to
 * /regenerate_sketches. Sketches are never sourced (enforced by the backend model).
 */
import type { ImageRef } from '../api/types';
import { ImageTile } from './ImageTile';

interface SketchGridProps {
  sketches: ImageRef[];
  onRegenerateSketch: (index: number) => void | Promise<void>;
  onRegenerateAll: () => void | Promise<void>;
  busy?: boolean;
}

export function SketchGrid({
  sketches,
  onRegenerateSketch,
  onRegenerateAll,
  busy,
}: SketchGridProps) {
  return (
    <section data-testid="sketch-grid" className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between">
        <h4 className="kicker">Sketches</h4>
        <button
          type="button"
          disabled={busy}
          onClick={() => onRegenerateAll()}
          className="btn-bare"
        >
          Regenerate all sketches
        </button>
      </header>
      <div className="grid grid-cols-3 gap-3">
        {sketches.map((sketch, index) => (
          <ImageTile
            key={`${sketch.url}-${index}`}
            image={sketch}
            busy={busy}
            onRegenerate={() => onRegenerateSketch(index)}
          />
        ))}
      </div>
    </section>
  );
}
