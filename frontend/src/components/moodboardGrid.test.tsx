import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MoodboardGrid } from './MoodboardGrid';
import type { ImageRef } from '../api/types';

function generated(i: number): ImageRef {
  return {
    kind: 'generated',
    url: `/generated/mb-gen-${i}.png`,
    provider: 'mock-image',
    license: 'internal',
    gen_model: 'mock-diffusion-v1',
    gen_prompt: `mood tile ${i}`,
    source_url: null,
    attribution: null,
    caption: null,
  };
}

function sourced(i: number): ImageRef {
  return {
    kind: 'sourced',
    url: `/generated/mb-src-${i}.png`,
    provider: 'Unsplash',
    license: 'Unsplash License',
    gen_model: null,
    gen_prompt: null,
    source_url: `https://unsplash.com/photos/${i}`,
    attribution: 'Jane Doe',
    caption: null,
  };
}

describe('<MoodboardGrid />', () => {
  it('renders one tile per moodboard item, each with a provenance tag', () => {
    const items = [generated(0), sourced(1), generated(2), sourced(3)];
    render(
      <MoodboardGrid
        moodboard={items}
        onRegenerateItem={vi.fn().mockResolvedValue(undefined)}
      />
    );
    const tiles = screen.getAllByTestId('image-tile');
    expect(tiles).toHaveLength(4);
    for (const tile of tiles) {
      expect(within(tile).getByTestId('provenance-tag')).toBeInTheDocument();
    }
  });

  it('generated tiles show "AI-generated · <model>"', () => {
    render(<MoodboardGrid moodboard={[generated(0)]} onRegenerateItem={vi.fn()} />);
    const tag = screen.getByTestId('provenance-tag');
    expect(tag).toHaveTextContent(/AI-generated/i);
    expect(tag).toHaveTextContent('mock-diffusion-v1');
  });

  it('sourced tiles show "<provider> · <license> · © <attribution>" and link the source_url', () => {
    render(<MoodboardGrid moodboard={[sourced(5)]} onRegenerateItem={vi.fn()} />);
    const tag = screen.getByTestId('provenance-tag');
    expect(tag).toHaveTextContent('Unsplash');
    expect(tag).toHaveTextContent('Unsplash License');
    expect(tag).toHaveTextContent('Jane Doe');
    const link = within(tag).getByRole('link');
    expect(link).toHaveAttribute('href', 'https://unsplash.com/photos/5');
  });

  it('per-tile ⟳ calls onRegenerateItem with the index and the tile kind', async () => {
    const onRegenerateItem = vi.fn().mockResolvedValue(undefined);
    render(
      <MoodboardGrid
        moodboard={[generated(0), sourced(1)]}
        onRegenerateItem={onRegenerateItem}
      />
    );
    const tiles = screen.getAllByTestId('image-tile');
    // regenerate the sourced tile (index 1), keeping its kind
    fireEvent.click(within(tiles[1]).getByRole('button', { name: /regenerate/i }));
    await waitFor(() =>
      expect(onRegenerateItem).toHaveBeenCalledWith({ index: 1, kind: 'sourced' })
    );
  });

  it('SourceToggle flips a generated tile to sourced, passing kind="sourced"', async () => {
    const onRegenerateItem = vi.fn().mockResolvedValue(undefined);
    render(<MoodboardGrid moodboard={[generated(0)]} onRegenerateItem={onRegenerateItem} />);
    const tile = screen.getByTestId('image-tile');
    // The SourceToggle for a generated tile offers "use sourced".
    fireEvent.click(within(tile).getByRole('button', { name: /sourced/i }));
    await waitFor(() =>
      expect(onRegenerateItem).toHaveBeenCalledWith({ index: 0, kind: 'sourced' })
    );
  });

  it('SourceToggle flips a sourced tile to generated, passing kind="generated"', async () => {
    const onRegenerateItem = vi.fn().mockResolvedValue(undefined);
    render(<MoodboardGrid moodboard={[sourced(0)]} onRegenerateItem={onRegenerateItem} />);
    const tile = screen.getByTestId('image-tile');
    fireEvent.click(within(tile).getByRole('button', { name: /generated/i }));
    await waitFor(() =>
      expect(onRegenerateItem).toHaveBeenCalledWith({ index: 0, kind: 'generated' })
    );
  });

  it('disables controls while busy (409 guard)', () => {
    render(<MoodboardGrid moodboard={[generated(0)]} busy onRegenerateItem={vi.fn()} />);
    expect(
      within(screen.getByTestId('image-tile')).getByRole('button', { name: /regenerate/i })
    ).toBeDisabled();
  });
});
