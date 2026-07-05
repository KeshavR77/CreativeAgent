/**
 * DirectionCard — the per-direction steering surface in the Cockpit (§14.2).
 * Shows the territory chip and brain badge; an EditableField for every §6.1
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

/** Read a dotted §6.1 editable field off a Direction. */
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
      className="rounded-full bg-indigo-900 px-2 py-0.5 text-[10px] text-indigo-100"
    >
      divergence {score == null ? '—' : score.toFixed(2)}
    </span>
  );
}

function CritiquePanel({ direction }: { direction: Direction }) {
  const c = direction.critique;
  return (
    <div
      data-testid="critique-panel"
      className="flex flex-col gap-1 rounded border border-slate-800 bg-slate-950 p-2"
    >
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-200">Critique</span>
        {direction.critique_stale ? (
          <span
            data-testid="stale-critique-badge"
            className="rounded bg-amber-800 px-1.5 py-0.5 text-[10px] text-amber-100"
          >
            stale — re-critique
          </span>
        ) : null}
      </div>
      {c ? (
        <>
          <div className="flex flex-wrap gap-2 text-[10px] text-slate-300">
            <span>verdict: {c.verdict}</span>
            <span>distinct {c.distinctiveness}</span>
            <span>fit {c.strategic_fit}</span>
            <span>memorable {c.memorability}</span>
            <span>resonance {c.audience_resonance}</span>
            <span>feasible {c.feasibility}</span>
            <span>· {c.critic_model}</span>
          </div>
          <p className="text-xs text-slate-400">{c.case_against}</p>
        </>
      ) : (
        <span className="text-[10px] text-slate-500">not yet critiqued</span>
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
  return (
    <article
      data-testid={`direction-card-${direction.id}`}
      className="flex flex-col gap-3 rounded-lg border border-slate-700 bg-slate-900 p-3"
    >
      {/* header: territory chip + brain badge + status */}
      <header className="flex flex-wrap items-center gap-2">
        <span
          data-testid="territory-chip"
          className="rounded-full bg-slate-700 px-2 py-0.5 text-xs font-semibold text-slate-100"
        >
          {direction.territory.label}
        </span>
        <span
          data-testid="brain-badge"
          data-brain={direction.brain}
          className={
            direction.brain === 'claude_high_temp'
              ? 'rounded bg-fuchsia-800 px-1.5 py-0.5 text-[10px] text-fuchsia-100'
              : 'rounded bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-200'
          }
        >
          {direction.brain}
        </span>
        <span className="text-[10px] uppercase text-slate-500">
          {direction.status}
        </span>
        <div className="ml-auto">
          <DivergenceBadge score={direction.divergence_score} />
        </div>
      </header>

      {/* candidate names + unscreened marker */}
      {names && names.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase text-slate-400">names</span>
          {names.map((n) => (
            <span
              key={n}
              className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-100"
            >
              {n}
            </span>
          ))}
          <span
            data-testid="unscreened-badge"
            title="Candidate names are not trademark-screened"
            className="rounded bg-rose-900 px-1.5 py-0.5 text-[10px] text-rose-100"
          >
            unscreened
          </span>
        </div>
      ) : null}

      {/* editable fields — inline edit + single-field regenerate (§19: coarse
          control is a product violation; single-field regen is required) */}
      <div className="grid grid-cols-1 gap-2">
        {EDITABLE_FIELDS.map((field) => (
          <div key={field} className="flex items-start gap-1">
            <div className="flex-1">
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
                className="mt-1 rounded bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-100 disabled:opacity-40"
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
      <footer className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onPromote(direction.id)}
          className="rounded bg-emerald-700 px-2 py-1 text-xs text-white disabled:opacity-40"
        >
          Promote
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onKill(direction.id)}
          className="rounded bg-rose-800 px-2 py-1 text-xs text-white disabled:opacity-40"
        >
          Kill
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onFork(direction.id)}
          className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-100 disabled:opacity-40"
        >
          Fork
        </button>
        {onRecritique ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onRecritique(direction.id)}
            className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-100 disabled:opacity-40"
          >
            Re-critique
          </button>
        ) : null}
        <label className="ml-auto flex items-center gap-1 text-xs text-slate-300">
          <input
            type="checkbox"
            aria-label="Select for merge"
            checked={!!mergeSelected}
            disabled={busy}
            onChange={() => onToggleMerge(direction.id)}
          />
          merge
        </label>
      </footer>
    </article>
  );
}
