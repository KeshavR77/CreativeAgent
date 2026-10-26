/**
 * DirectionCard — the per-direction steering surface in the Cockpit.
 * Shows the territory chip and brain badge; an EditableField for every
 * editable field; the DivergenceBadge; the CritiquePanel with a StaleCritiqueBadge
 * (raised only when critique_stale — visual regen never stales a critique);
 * candidate names with an UnscreenedBadge; the SketchGrid and MoodboardGrid (each
 * image carrying provenance); and promote/kill/fork/merge-select actions, all
 * disabled while a per-project op is in flight (409 guard).
 */
import type { Direction, ImageKind } from '../api/types';
import { EDITABLE_FIELDS } from '../api/types';
import { EditableField } from './EditableField';
import { SketchGrid } from './SketchGrid';
import { MoodboardGrid } from './MoodboardGrid';

type FieldValue = string | string[];

interface DirectionCardProps {
  direction: Direction;
  names?: string[];
  busy?: boolean;
  onPromote: (id: string) => void;
  onKill: (id: string) => void;
  onFork: (id: string) => void;
  onToggleMerge: (id: string) => void;
  onEditField: (id: string, payload: { field: string; value: FieldValue }) => Promise<void>;
  onRegenerateField?: (id: string, field: string) => Promise<void>;
  onRecritique?: (id: string) => Promise<void>;
  onRegenerateSketch: (id: string, index: number) => Promise<void>;
  onRegenerateAllSketches: (id: string) => Promise<void>;
  onRegenerateMoodboardItem: (
    id: string,
    args: { index: number; kind: ImageKind }
  ) => Promise<void>;
  mergeSelected?: boolean;
}

/** Read a dotted editable field off a Direction. */
function readField(direction: Direction, field: string): FieldValue {
  switch (field) {
    case 'big_idea':
      return direction.big_idea;
    case 'copy.headline':
      return direction.copy.headline;
    case 'copy.subhead':
      return direction.copy.subhead;
    case 'copy.body':
      return direction.copy.body;
    case 'copy.cta':
      return direction.copy.cta;
    case 'art_direction.imagery_direction':
      return direction.art_direction.imagery_direction;
    case 'art_direction.layout_notes':
      return direction.art_direction.layout_notes;
    case 'art_direction.mood_descriptors':
      return direction.art_direction.mood_descriptors;
    default:
      return '';
  }
}

function DivergenceBadge({ score }: { score: number | null }) {
  return (
    <span
      data-testid="divergence-badge"
      className="font-mono text-[10px] uppercase tracking-kicker text-muted"
    >
      divergence{' '}
      <span className="text-ink">{score == null ? '—' : score.toFixed(2)}</span>
    </span>
  );
}

function ScorePair({ label, value }: { label: string; value: number }) {
  return (
    <span className="whitespace-nowrap">
      {label} <span className="text-ink">{value}</span>
    </span>
  );
}

function CritiquePanel({ direction }: { direction: Direction }) {
  const c = direction.critique;
  return (
    <div
      data-testid="critique-panel"
      className="flex flex-col gap-1.5 border-l-2 border-line py-1 pl-4"
    >
      <div className="flex items-center gap-2">
        <span className="kicker">Critique</span>
        {direction.critique_stale ? (
          <span
            data-testid="stale-critique-badge"
            className="rounded-sm bg-warnSoft px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-kicker text-warn"
          >
            stale — re-critique
          </span>
        ) : null}
      </div>
      {c ? (
        <>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted">
            <span className="whitespace-nowrap">
              verdict{' '}
              <span className={c.verdict === 'ship' ? 'text-ok' : c.verdict === 'kill' ? 'text-accent' : 'text-warn'}>
                {c.verdict}
              </span>
            </span>
            <ScorePair label="distinct" value={c.distinctiveness} />
            <ScorePair label="fit" value={c.strategic_fit} />
            <ScorePair label="memorable" value={c.memorability} />
            <ScorePair label="resonance" value={c.audience_resonance} />
            <ScorePair label="feasible" value={c.feasibility} />
            <span className="text-faint">· {c.critic_model}</span>
          </div>
          <p className="text-[13px] leading-relaxed text-ink-soft">{c.case_against}</p>
        </>
      ) : (
        <span className="font-mono text-[10px] text-faint">not yet critiqued</span>
      )}
    </div>
  );
}

export function DirectionCard({
  direction,
  names,
  busy,
  onPromote,
  onKill,
  onFork,
  onToggleMerge,
  onEditField,
  onRegenerateField,
  onRegenerateSketch,
  onRegenerateAllSketches,
  onRegenerateMoodboardItem,
  onRecritique,
  mergeSelected,
}: DirectionCardProps) {
  const dead = direction.status === 'killed';
  return (
    <article
      data-testid={`direction-card-${direction.id}`}
      className={`panel flex flex-col gap-5 p-6 ${dead ? 'opacity-50' : ''} ${
        mergeSelected ? 'border-ink' : ''
      }`}
    >
      {/* header: territory + brain + status + divergence */}
      <header className="flex flex-wrap items-baseline gap-3">
        <h3 data-testid="territory-chip" className="font-serif text-xl text-ink">
          {direction.territory.label}
        </h3>
        <span
          data-testid="brain-badge"
          data-brain={direction.brain}
          className={`font-mono text-[10px] uppercase tracking-kicker ${
            direction.brain === 'claude_high_temp' ? 'text-warn' : 'text-muted'
          }`}
        >
          {direction.brain}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-kicker text-faint">
          {direction.status}
        </span>
        <div className="ml-auto">
          <DivergenceBadge score={direction.divergence_score} />
        </div>
      </header>

      {/* candidate names + unscreened marker */}
      {names && names.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="kicker">names</span>
          {names.map((n) => (
            <span key={n} className="rounded-sm border border-line px-2 py-0.5 text-xs text-ink">
              {n}
            </span>
          ))}
          <span
            data-testid="unscreened-badge"
            title="Candidate names are not trademark-screened"
            className="rounded-sm bg-accent-soft px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-kicker text-accent"
          >
            unscreened
          </span>
        </div>
      ) : null}

      {/* editable fields — inline edit + single-field regenerate (coarse
          control is a product violation; single-field regen is required) */}
      <div className="grid grid-cols-1 gap-0">
        {EDITABLE_FIELDS.map((field) => (
          <div key={field} className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <EditableField
                field={field}
                value={readField(direction, field)}
                disabled={busy}
                onSave={(payload) => onEditField(direction.id, payload)}
              />
            </div>
            {onRegenerateField ? (
              <button
                type="button"
                aria-label={`Regenerate ${field}`}
                title={`Regenerate ${field}`}
                disabled={busy}
                onClick={() => onRegenerateField(direction.id, field)}
                className="btn-bare mt-2"
              >
                ⟳
              </button>
            ) : null}
          </div>
        ))}
      </div>

      {/* critique */}
      <CritiquePanel direction={direction} />

      {/* sketches (always generated/placeholder) */}
      <SketchGrid
        sketches={direction.sketches}
        busy={busy}
        onRegenerateSketch={(index) => onRegenerateSketch(direction.id, index)}
        onRegenerateAll={() => onRegenerateAllSketches(direction.id)}
      />

      {/* moodboard (mixed provenance) */}
      <MoodboardGrid
        moodboard={direction.art_direction.moodboard}
        busy={busy}
        onRegenerateItem={(args) => onRegenerateMoodboardItem(direction.id, args)}
      />

      {/* actions */}
      <footer className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
        <button
          type="button"
          disabled={busy}
          onClick={() => onPromote(direction.id)}
          className="btn-ink"
        >
          Promote
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onFork(direction.id)}
          className="btn-ghost"
        >
          Fork
        </button>
        {onRecritique ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onRecritique(direction.id)}
            className="btn-ghost"
          >
            Re-critique
          </button>
        ) : null}
        <button
          type="button"
          disabled={busy}
          onClick={() => onKill(direction.id)}
          className="btn-danger"
        >
          Kill
        </button>
        <label className="ml-auto flex cursor-pointer items-center gap-2 font-mono text-[10px] uppercase tracking-kicker text-muted">
          <input
            type="checkbox"
            aria-label="Select for merge"
            checked={!!mergeSelected}
            disabled={busy}
            onChange={() => onToggleMerge(direction.id)}
            className="accent-ink"
          />
          merge
        </label>
      </footer>
    </article>
  );
}
