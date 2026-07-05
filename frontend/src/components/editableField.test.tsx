import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EditableField } from './EditableField';

describe('<EditableField /> inline edit', () => {
  it('renders the current value and the field label', () => {
    render(
      <EditableField
        field="big_idea"
        value="original idea"
        onSave={vi.fn().mockResolvedValue(undefined)}
      />
    );
    expect(screen.getByText('original idea')).toBeInTheDocument();
    expect(screen.getByText(/big_idea/i)).toBeInTheDocument();
  });

  it('reflects an external value change (e.g. single-field regenerate) via the value prop', () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <EditableField field="big_idea" value="original idea" onSave={onSave} />
    );
    expect(screen.getByText('original idea')).toBeInTheDocument();
    // Parent re-renders with a server-regenerated value while this field is
    // mounted in read mode — it must show the new value, not the stale one.
    rerender(<EditableField field="big_idea" value="regenerated idea" onSave={onSave} />);
    expect(screen.getByText('regenerated idea')).toBeInTheDocument();
    expect(screen.queryByText('original idea')).not.toBeInTheDocument();
  });

  it('enters edit mode, and Save fires onSave with the {field, value} payload shape', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<EditableField field="copy.headline" value="old headline" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new headline' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    // The payload the backend /edit endpoint expects: { field, value }.
    expect(onSave).toHaveBeenCalledWith({ field: 'copy.headline', value: 'new headline' });
  });

  it('optimistically shows the new value before the save resolves, then confirms', async () => {
    let resolve!: () => void;
    const onSave = vi.fn().mockReturnValue(new Promise<void>((r) => (resolve = r)));
    render(<EditableField field="big_idea" value="v0" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'v1' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    // Optimistic: the new value is visible while the request is in flight...
    expect(await screen.findByText('v1')).toBeInTheDocument();
    // ...and it's marked pending (not yet confirmed).
    expect(screen.getByTestId('editable-big_idea')).toHaveAttribute('data-pending', 'true');

    resolve();
    await waitFor(() =>
      expect(screen.getByTestId('editable-big_idea')).toHaveAttribute('data-pending', 'false')
    );
  });

  it('rolls back the optimistic value if the save rejects', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('409'));
    render(<EditableField field="big_idea" value="keep-me" onSave={onSave} />);

    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'discard-me' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => expect(screen.getByText('keep-me')).toBeInTheDocument());
    expect(screen.queryByText('discard-me')).not.toBeInTheDocument();
  });

  it('array-valued fields (mood_descriptors) round-trip as an array in the payload', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EditableField
        field="art_direction.mood_descriptors"
        value={['bold', 'airy']}
        onSave={onSave}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'bold, airy, warm' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith({
      field: 'art_direction.mood_descriptors',
      value: ['bold', 'airy', 'warm'],
    });
  });
});
