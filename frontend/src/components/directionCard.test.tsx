import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { DirectionCard } from './DirectionCard';
import type { Direction, CritiqueScore, ImageRef } from '../api/types';

function critique(overrides: Partial<CritiqueScore> = {}): CritiqueScore {
  return {
    distinctiveness: 4,
    strategic_fit: 4,
    memorability: 3,
    audience_resonance: 4,
    feasibility: 5,
    case_against:
      'This concept leans on a visual trope that competitors already own, so the ' +
      'distinctiveness is thinner than it looks and the audience may not remember it ' +
      'past a single exposure without far more media weight behind the launch push.',
    verdict: 'revise',
    critic_model: 'mock-critic',
    ...overrides,
  };
}

function genSketch(): ImageRef {
  return {
    kind: 'generated',
    url: '/generated/s1.png',
    provider: 'mock-image',
    license: 'internal',
    gen_model: 'mock-diffusion',
    gen_prompt: 'a bold poster',
    source_url: null,
    attribution: null,
    caption: null,
  };
}

function makeDirection(overrides: Partial<Direction> = {}): Direction {
  return {
    id: 'd1',
    territory: { label: 'Rebel Optimism', lens: 'defiant hope', description: '' },
    big_idea: 'Dare to glow',
    brain: 'claude_high_temp',
    art_direction: {
      mood_descriptors: ['bold', 'warm'],
      imagery_direction: 'sun-drenched portraits',
      layout_notes: 'asymmetric grid',
      palette: [{ name: 'Ember', hex: '#FF5522', role: 'primary' }],
      typography: [{ role: 'display', family: 'Grotesk', fallback: '', weights: [] }],
      moodboard: [],
    },
    copy: { headline: 'Glow up', subhead: 'sub', body: 'body', taglines: [], cta: 'Join' },
    sketches: [genSketch()],
    critique: critique(),
    critique_stale: false,
    divergence_score: 0.42,
    status: 'draft',
    annotations: [],
    parent_id: null,
    merged_from: [],
    lens_tweak: null,
    ...overrides,
  };
}

const noopActions = {
  onPromote: vi.fn(),
  onKill: vi.fn(),
  onFork: vi.fn(),
  onEditField: vi.fn().mockResolvedValue(undefined),
  onRegenerateField: vi.fn().mockResolvedValue(undefined),
  onRecritique: vi.fn().mockResolvedValue(undefined),
  onToggleMerge: vi.fn(),
  onRegenerateSketch: vi.fn().mockResolvedValue(undefined),
  onRegenerateAllSketches: vi.fn().mockResolvedValue(undefined),
  onRegenerateMoodboardItem: vi.fn().mockResolvedValue(undefined),
};

describe('<DirectionCard />', () => {
  it('renders the territory label as a chip and the brain badge', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    expect(screen.getByText('Rebel Optimism')).toBeInTheDocument();
    // claude_high_temp gets a distinct badge (mode transparency).
    expect(screen.getByText(/claude_high_temp/i)).toBeInTheDocument();
  });

  it('renders an EditableField for every §6.1 editable field', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    for (const f of [
      'big_idea',
      'copy.headline',
      'copy.subhead',
      'copy.body',
      'copy.cta',
      'art_direction.imagery_direction',
      'art_direction.layout_notes',
      'art_direction.mood_descriptors',
    ]) {
      expect(screen.getByTestId(`editable-${f}`)).toBeInTheDocument();
    }
  });

  it('shows the DivergenceBadge with the direction score', () => {
    render(<DirectionCard direction={makeDirection({ divergence_score: 0.42 })} {...noopActions} />);
    expect(screen.getByTestId('divergence-badge')).toHaveTextContent('0.42');
  });

  it('shows a StaleCritiqueBadge only when critique_stale is true', () => {
    const { rerender } = render(
      <DirectionCard direction={makeDirection({ critique_stale: false })} {...noopActions} />
    );
    expect(screen.queryByTestId('stale-critique-badge')).not.toBeInTheDocument();

    rerender(<DirectionCard direction={makeDirection({ critique_stale: true })} {...noopActions} />);
    expect(screen.getByTestId('stale-critique-badge')).toBeInTheDocument();
  });

  it('renders the CritiquePanel with the verdict and the case_against', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    const panel = screen.getByTestId('critique-panel');
    expect(within(panel).getByText(/revise/i)).toBeInTheDocument();
    expect(within(panel).getByText(/competitors already own/i)).toBeInTheDocument();
  });

  it('shows an UnscreenedBadge on candidate names', () => {
    render(
      <DirectionCard
        direction={makeDirection()}
        names={['Glowform', 'Emberly']}
        {...noopActions}
      />
    );
    expect(screen.getByTestId('unscreened-badge')).toBeInTheDocument();
    expect(screen.getByText('Glowform')).toBeInTheDocument();
  });

  it('wires promote / kill / fork actions', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    fireEvent.click(screen.getByRole('button', { name: /promote/i }));
    fireEvent.click(screen.getByRole('button', { name: /kill/i }));
    fireEvent.click(screen.getByRole('button', { name: /fork/i }));
    expect(noopActions.onPromote).toHaveBeenCalledWith('d1');
    expect(noopActions.onKill).toHaveBeenCalledWith('d1');
    expect(noopActions.onFork).toHaveBeenCalledWith('d1');
  });

  it('wires the merge-select toggle for this direction id', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    fireEvent.click(screen.getByRole('checkbox', { name: /merge/i }));
    expect(noopActions.onToggleMerge).toHaveBeenCalledWith('d1');
  });

  it('editing a field goes through onEditField with the {field, value} payload', async () => {
    const onEditField = vi.fn().mockResolvedValue(undefined);
    render(<DirectionCard direction={makeDirection()} {...noopActions} onEditField={onEditField} />);

    const bigIdea = screen.getByTestId('editable-big_idea');
    fireEvent.click(within(bigIdea).getByRole('button', { name: /edit/i }));
    fireEvent.change(within(bigIdea).getByRole('textbox'), { target: { value: 'Dare to shine' } });
    fireEvent.click(within(bigIdea).getByRole('button', { name: /save/i }));

    await waitFor(() => expect(onEditField).toHaveBeenCalledWith('d1', { field: 'big_idea', value: 'Dare to shine' }));
  });

  it('single-field regenerate is reachable and calls onRegenerateField(id, field)', () => {
    const onRegenerateField = vi.fn().mockResolvedValue(undefined);
    render(
      <DirectionCard direction={makeDirection()} {...noopActions} onRegenerateField={onRegenerateField} />
    );
    fireEvent.click(screen.getByRole('button', { name: /regenerate big_idea/i }));
    expect(onRegenerateField).toHaveBeenCalledWith('d1', 'big_idea');
  });

  it('every sketch tile carries a provenance tag (never an untagged image)', () => {
    render(<DirectionCard direction={makeDirection()} {...noopActions} />);
    const tiles = screen.getAllByTestId('image-tile');
    for (const tile of tiles) {
      expect(within(tile).getByTestId('provenance-tag')).toBeInTheDocument();
    }
  });

  it('disables actions while a per-project op is in flight (409 guard)', () => {
    render(<DirectionCard direction={makeDirection()} busy {...noopActions} />);
    expect(screen.getByRole('button', { name: /promote/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /kill/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /fork/i })).toBeDisabled();
  });
});
