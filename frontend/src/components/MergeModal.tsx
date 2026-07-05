/**
 * MergeModal — pick, per field, which parent direction contributes to the merged
 * child (§14.2). The moodboard is chosen as a WHOLE board (A/B), not per tile.
 * Sketches are deliberately excluded — they are auto-regenerated for the merged
 * direction post-merge, so offering them as a choice would be meaningless.
 *
 * Submits the backend /directions/merge body: { direction_ids, field_choices }.
 */
import { useMemo, useState } from 'react';
import type { Direction } from '../api/types';
import { EDITABLE_FIELDS } from '../api/types';

// The fields a merge may choose a source for: the editable text/color/type fields
// plus a whole-board moodboard pick. NOT sketches (auto-regenerated post-merge).
const MERGE_FIELDS = [...EDITABLE_FIELDS, 'moodboard'] as const;

interface MergeModalProps {
  directions: Direction[];
  onMerge: (body: {
    direction_ids: string[];
    field_choices: Record<string, string>;
  }) => Promise<void>;
  onClose: () => void;
}

export function MergeModal({ directions, onMerge, onClose }: MergeModalProps) {
  const ids = useMemo(() => directions.map((d) => d.id), [directions]);
  // default every field to the first parent.
  const [choices, setChoices] = useState<Record<string, string>>(() =>
    Object.fromEntries(MERGE_FIELDS.map((f) => [f, ids[0]]))
  );
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await onMerge({ direction_ids: ids, field_choices: choices });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Merge directions"
      data-testid="merge-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-slate-900 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-100">
            Merge directions
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-slate-400"
          >
            Close
          </button>
        </div>

        <p className="mb-3 text-xs text-slate-400">
          Choose which parent contributes each field. The moodboard is picked as a
          whole board.
        </p>

        <div className="flex flex-col gap-2">
          {MERGE_FIELDS.map((field) => (
            <div
              key={field}
              data-testid={`merge-field-${field}`}
              className="flex items-center justify-between gap-4 rounded border border-slate-800 p-2"
            >
              <span className="text-xs font-medium text-slate-200">
                {field === 'moodboard' ? 'moodboard (whole board)' : field}
              </span>
              <div className="flex gap-3">
                {directions.map((d) => (
                  <label
                    key={d.id}
                    className="flex items-center gap-1 text-xs text-slate-300"
                  >
                    <input
                      type="radio"
                      name={`merge-${field}`}
                      aria-label={`choose ${d.id}`}
                      checked={choices[field] === d.id}
                      onChange={() =>
                        setChoices((prev) => ({ ...prev, [field]: d.id }))
                      }
                    />
                    {d.id}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-slate-700 px-3 py-1 text-sm text-slate-100"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={submit}
            className="rounded bg-emerald-700 px-3 py-1 text-sm text-white disabled:opacity-40"
          >
            Merge
          </button>
        </div>
      </div>
    </div>
  );
}
