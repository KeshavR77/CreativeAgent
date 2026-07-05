import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MergeModal } from './MergeModal';
import type { Direction } from '../api/types';

function makeDirection(id: string, headline: string, idea: string): Direction {
  return {
    id,
    territory: { label: 'T-' + id, lens: 'lens', description: '' },
    big_idea: idea,
    brain: 'mock',
    art_direction: {
      mood_descriptors: [],
      imagery_direction: 'imagery-' + id,
      layout_notes: 'layout-' + id,
      palette: [],
      typography: [],
      moodboard: [
        {
          kind: 'generated',
          url: `/generated/${id}-mb.png`,
          provider: 'mock-image',
          license: 'internal',
          gen_model: 'mock',
          gen_prompt: 'p',
          source_url: null,
          attribution: null,
          caption: null,
        },
      ],
    },
    copy: { headline, subhead: '', body: '', taglines: [], cta: '' },
    sketches: [],
    critique: null,
    critique_stale: false,
    divergence_score: null,
    status: 'draft',
    annotations: [],
    parent_id: null,
    merged_from: [],
    lens_tweak: null,
  };
}

const A = makeDirection('dA', 'Headline A', 'Idea A');
const B = makeDirection('dB', 'Headline B', 'Idea B');

describe('<MergeModal />', () => {
  it('lets you pick, per field, which parent contributes and submits field_choices', async () => {
    const onMerge = vi.fn().mockResolvedValue(undefined);
    render(<MergeModal directions={[A, B]} onMerge={onMerge} onClose={vi.fn()} />);

    // For big_idea, pick parent B; for copy.headline, pick parent A (default).
    const bigIdeaRow = screen.getByTestId('merge-field-big_idea');
    fireEvent.click(within(bigIdeaRow).getByRole('radio', { name: /dB/i }));

    fireEvent.click(screen.getByRole('button', { name: /merge/i }));

    await waitFor(() => expect(onMerge).toHaveBeenCalledTimes(1));
    const body = onMerge.mock.calls[0][0];
    expect(body.direction_ids).toEqual(['dA', 'dB']);
    expect(body.field_choices.big_idea).toBe('dB');
    expect(body.field_choices['copy.headline']).toBe('dA');
  });

  it('offers a whole-board moodboard A/B choice (not per-tile)', async () => {
    const onMerge = vi.fn().mockResolvedValue(undefined);
    render(<MergeModal directions={[A, B]} onMerge={onMerge} onClose={vi.fn()} />);

    const moodboardRow = screen.getByTestId('merge-field-moodboard');
    // whole-board choice: one radio per parent, picking that parent's entire board.
    fireEvent.click(within(moodboardRow).getByRole('radio', { name: /dB/i }));

    fireEvent.click(screen.getByRole('button', { name: /merge/i }));
    await waitFor(() => expect(onMerge).toHaveBeenCalled());
    expect(onMerge.mock.calls[0][0].field_choices.moodboard).toBe('dB');
  });

  it('never offers sketches as a merge choice (auto-regenerated post-merge)', () => {
    render(<MergeModal directions={[A, B]} onMerge={vi.fn()} onClose={vi.fn()} />);
    expect(screen.queryByTestId('merge-field-sketches')).not.toBeInTheDocument();
    // and no field_choices key should mention sketches
    expect(screen.queryByText(/sketch/i)).not.toBeInTheDocument();
  });

  it('submits field_choices for every offered editable + moodboard field', async () => {
    const onMerge = vi.fn().mockResolvedValue(undefined);
    render(<MergeModal directions={[A, B]} onMerge={onMerge} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /merge/i }));
    await waitFor(() => expect(onMerge).toHaveBeenCalled());
    const choices = onMerge.mock.calls[0][0].field_choices;
    for (const f of [
      'big_idea',
      'copy.headline',
      'copy.subhead',
      'copy.body',
      'copy.cta',
      'art_direction.imagery_direction',
      'art_direction.layout_notes',
      'art_direction.mood_descriptors',
      'moodboard',
    ]) {
      expect(choices).toHaveProperty(f);
    }
    expect(choices).not.toHaveProperty('sketches');
  });
});
