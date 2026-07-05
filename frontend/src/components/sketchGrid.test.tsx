import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { SketchGrid } from './SketchGrid';
import type { ImageRef } from '../api/types';

function gen(i: number): ImageRef {
  return {
    kind: 'generated',
    url: `/generated/sketch-${i}.png`,
    provider: 'mock-image',
    license: 'internal',
    gen_model: 'mock-diffusion-v1',
    gen_prompt: `bold concept sketch ${i}`,
    source_url: null,
    attribution: null,
    caption: null,
  };
}

function placeholder(i: number): ImageRef {
  return {
    kind: 'placeholder',
    url: `/generated/placeholder-${i}.png`,
    provider: 'placeholder',
    license: 'none',
    gen_model: null,
    gen_prompt: null,
    source_url: null,
    attribution: null,
    caption: 'image-gen unavailable',
  };
}

describe('<SketchGrid />', () => {
  it('renders one tile per sketch, each with a provenance tag', () => {
    const sketches = [gen(0), gen(1), gen(2), gen(3)];
    render(
      <SketchGrid
        sketches={sketches}
        onRegenerateSketch={vi.fn().mockResolvedValue(undefined)}
        onRegenerateAll={vi.fn().mockResolvedValue(undefined)}
      />
    );
    const tiles = screen.getAllByTestId('image-tile');
    expect(tiles).toHaveLength(4);
    for (const tile of tiles) {
      expect(within(tile).getByTestId('provenance-tag')).toBeInTheDocument();
    }
  });

  it('generated tiles show "AI-generated · <model>" and expose the prompt on hover', () => {
    render(
      <SketchGrid
        sketches={[gen(0)]}
        onRegenerateSketch={vi.fn()}
        onRegenerateAll={vi.fn()}
      />
    );
    const tag = screen.getByTestId('provenance-tag');
    expect(tag).toHaveTextContent(/AI-generated/i);
    expect(tag).toHaveTextContent('mock-diffusion-v1');
    // prompt available via title attribute (hover)
    expect(screen.getByTestId('image-tile')).toHaveAttribute('title', expect.stringContaining('bold concept sketch 0'));
  });

  it('a placeholder tile is explicitly labeled as a placeholder', () => {
    render(
      <SketchGrid
        sketches={[placeholder(0)]}
        onRegenerateSketch={vi.fn()}
        onRegenerateAll={vi.fn()}
      />
    );
    expect(screen.getByTestId('provenance-tag')).toHaveTextContent(/placeholder/i);
  });

  it('per-tile ⟳ calls onRegenerateSketch with that tile index', async () => {
    const onRegenerateSketch = vi.fn().mockResolvedValue(undefined);
    render(
      <SketchGrid
        sketches={[gen(0), gen(1), gen(2)]}
        onRegenerateSketch={onRegenerateSketch}
        onRegenerateAll={vi.fn()}
      />
    );
    const tiles = screen.getAllByTestId('image-tile');
    fireEvent.click(within(tiles[2]).getByRole('button', { name: /regenerate/i }));
    await waitFor(() => expect(onRegenerateSketch).toHaveBeenCalledWith(2));
  });

  it('"Regenerate all" calls onRegenerateAll', async () => {
    const onRegenerateAll = vi.fn().mockResolvedValue(undefined);
    render(
      <SketchGrid
        sketches={[gen(0), gen(1)]}
        onRegenerateSketch={vi.fn()}
        onRegenerateAll={onRegenerateAll}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /regenerate all/i }));
    await waitFor(() => expect(onRegenerateAll).toHaveBeenCalledTimes(1));
  });

  it('disables regeneration controls while busy (409 guard)', () => {
    render(
      <SketchGrid
        sketches={[gen(0)]}
        busy
        onRegenerateSketch={vi.fn()}
        onRegenerateAll={vi.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /regenerate all/i })).toBeDisabled();
    expect(
      within(screen.getByTestId('image-tile')).getByRole('button', { name: /regenerate/i })
    ).toBeDisabled();
  });
});
