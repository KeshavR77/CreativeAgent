/**
 * EditableField — inline edit for one.1-editable field. Read mode shows the
 * label + current value; Edit swaps in a textbox; Save emits the backend /edit
 * payload shape `{ field, value }`. The value is applied optimistically (marked
 * data-pending) and rolled back if the save rejects (e.g. a 409 mid-flight).
 *
 * Array-valued fields (art_direction.mood_descriptors) round-trip as a
 * comma-separated string in the input and an array in the payload.
 */
import { useEffect, useState } from 'react';
import type { EditableField as EditableFieldName } from '../api/types';

type FieldValue = string | string[];

interface EditableFieldProps {
  field: EditableFieldName | string;
  value: FieldValue;
  onSave: (payload: { field: string; value: FieldValue }) => Promise<void>;
  label?: string;
  disabled?: boolean;
}

const isArrayValue = (v: FieldValue): v is string[] => Array.isArray(v);

const toText = (v: FieldValue): string =>
  isArrayValue(v) ? v.join(', ') : (v ?? '');

const fromText = (text: string, wasArray: boolean): FieldValue =>
  wasArray
    ? text
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
    : text;

const displayText = (v: FieldValue): string =>
  isArrayValue(v) ? v.join(', ') : (v ?? '');

export function EditableField({
  field,
  value,
  onSave,
  label,
  disabled,
}: EditableFieldProps) {
  const wasArray = isArrayValue(value);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => toText(value));
  const [display, setDisplay] = useState<FieldValue>(value);
  const [pending, setPending] = useState(false);

  // Re-sync display when the value prop changes from OUTSIDE the component
  // (single-field regenerate, merge/fork refetch, another client's edit) — but
  // never clobber an in-progress edit or an optimistic pending save.
  useEffect(() => {
    if (!editing && !pending) setDisplay(value);
  }, [value, editing, pending]);

  const startEdit = () => {
    setDraft(toText(display));
    setEditing(true);
  };

  const save = async () => {
    const nextValue = fromText(draft, wasArray);
    const previous = display;
    setEditing(false);
    setDisplay(nextValue); // optimistic
    setPending(true);
    try {
      await onSave({ field, value: nextValue });
      setPending(false); // confirmed
    } catch {
      setDisplay(previous); // rollback
      setPending(false);
    }
  };

  return (
    <div
      data-testid={`editable-${field}`}
      data-pending={pending ? 'true' : 'false'}
      className="group/field flex flex-col gap-1 border-b border-line py-2"
    >
      <div className="flex items-center justify-between">
        <span className="kicker">{label ?? field}</span>
        {!editing ? (
          <button
            type="button"
            disabled={disabled}
            onClick={startEdit}
            className="btn-bare opacity-0 transition-opacity focus:opacity-100 group-hover/field:opacity-100"
          >
            Edit
          </button>
        ) : null}
      </div>

      {editing ? (
        <div className="flex flex-col gap-2">
          <textarea
            aria-label={`Edit ${field}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="field"
            rows={2}
          />
          <div className="flex gap-2">
            <button type="button" onClick={save} className="btn-ink">
              Save
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="btn-ghost"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <span className={`text-[14px] leading-relaxed text-ink ${pending ? 'opacity-60' : ''}`}>
          {displayText(display)}
        </span>
      )}
    </div>
  );
}
