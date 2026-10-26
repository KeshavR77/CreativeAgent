/**
 * MoodboardGrid — 4–8 tiles tagged by kind. Generated tiles show
 * "AI-generated · <model>"; sourced tiles show "<provider> · <license> ·
 * © <attribution>" linking source_url. Per-tile ⟳ maps to
 * /regenerate_moodboard_item{index, kind}; the SourceToggle regenerates the same
 * tile with the opposite kind (generated ⇄ sourced), passing `kind` so the backend
 * swaps generation mode. Every tile keeps its ProvenanceTag.
 */
import type { ImageKind, ImageRef } from '../api/types';
import { ImageTile } from './ImageTile';

export interface MoodboardRegenArgs {
  index: number;
  kind: ImageKind;
}

interface MoodboardGridProps {
  moodboard: ImageRef[];
  onRegenerateItem: (args: MoodboardRegenArgs) => void | Promise<void>;
  busy?: boolean;
}

function SourceToggle({
  current,
  disabled,
  onSwap,
}: {
  current: ImageKind;
  disabled?: boolean;
  onSwap: (kind: ImageKind) => void;
}) {
  // Only generated <-> sourced are swappable; placeholders aren't a user choice.
  if (current === 'placeholder') return null;
  const target: ImageKind = current === 'generated' ? 'sourced' : 'generated';
  const label = target === 'sourced' ? 'Use sourced' : 'Use generated';
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSwap(target)}
      className="btn-bare self-start"
    >
      {label}
    </button>
  );
}

export function MoodboardGrid({
  moodboard,
  onRegenerateItem,
  busy,
}: MoodboardGridProps) {
  return (
    <section data-testid="moodboard-grid" className="flex flex-col gap-2">
      <h4 className="kicker">Moodboard</h4>
      <div className="grid grid-cols-4 gap-3">
        {moodboard.map((item, index) => (
          <ImageTile
            key={`${item.url}-${index}`}
            image={item}
            busy={busy}
            onRegenerate={() => onRegenerateItem({ index, kind: item.kind })}
            controls={
              <SourceToggle
                current={item.kind}
                disabled={busy}
                onSwap={(kind) => onRegenerateItem({ index, kind })}
              />
            }
          />
        ))}
      </div>
    </section>
  );
}
