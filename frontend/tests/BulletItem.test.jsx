import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DndContext } from '@dnd-kit/core';
import { SortableContext } from '@dnd-kit/sortable';
import { vi } from 'vitest';
import { BulletItem } from '../src/components/BulletItem';

const bullet = { id: 1, text: 'Test bullet point', sort_order: 0 };

function renderBullet(onUpdate = vi.fn(), onDelete = vi.fn()) {
  return render(
    <DndContext>
      <SortableContext items={[1]}>
        <ul>
          <BulletItem bullet={bullet} onUpdate={onUpdate} onDelete={onDelete} disabled={false} />
        </ul>
      </SortableContext>
    </DndContext>
  );
}

describe('BulletItem', () => {
  it('renders bullet text', () => {
    renderBullet();
    expect(screen.getByText('Test bullet point')).toBeInTheDocument();
  });

  it('has an edit button with accessible label', () => {
    renderBullet();
    expect(screen.getByRole('button', { name: /edit: test bullet point/i })).toBeInTheDocument();
  });

  it('has a delete button with accessible label', () => {
    renderBullet();
    expect(screen.getByRole('button', { name: /delete: test bullet point/i })).toBeInTheDocument();
  });

  it('has a drag handle with accessible label', () => {
    renderBullet();
    expect(screen.getByRole('button', { name: /drag to reorder/i })).toBeInTheDocument();
  });

  it('enters edit mode on edit button click', async () => {
    renderBullet();
    fireEvent.click(screen.getByRole('button', { name: /edit: test bullet point/i }));
    const input = await screen.findByRole('textbox', { name: /edit bullet text/i });
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('Test bullet point');
  });

  it('calls onUpdate on Enter key', async () => {
    const onUpdate = vi.fn().mockResolvedValue({ id: 1, text: 'Updated text', sort_order: 0 });
    renderBullet(onUpdate);
    fireEvent.click(screen.getByRole('button', { name: /edit: test bullet point/i }));
    const input = await screen.findByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, 'Updated text');
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(1, 'Updated text'));
  });

  it('calls onUpdate on save button click', async () => {
    const onUpdate = vi.fn().mockResolvedValue({ id: 1, text: 'New text', sort_order: 0 });
    renderBullet(onUpdate);
    fireEvent.click(screen.getByRole('button', { name: /edit: test bullet point/i }));
    const input = await screen.findByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, 'New text');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(1, 'New text'));
  });

  it('cancels edit on Escape', async () => {
    renderBullet();
    fireEvent.click(screen.getByRole('button', { name: /edit: test bullet point/i }));
    const input = await screen.findByRole('textbox');
    fireEvent.keyDown(input, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      expect(screen.getByText('Test bullet point')).toBeInTheDocument();
    });
  });

  it('does not call onUpdate if text unchanged', async () => {
    const onUpdate = vi.fn();
    renderBullet(onUpdate);
    fireEvent.click(screen.getByRole('button', { name: /edit: test bullet point/i }));
    await screen.findByRole('textbox');
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    await waitFor(() => expect(onUpdate).not.toHaveBeenCalled());
  });

  it('calls onDelete on delete button click', () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    renderBullet(vi.fn(), onDelete);
    fireEvent.click(screen.getByRole('button', { name: /delete: test bullet point/i }));
    expect(onDelete).toHaveBeenCalledWith(1);
  });

  it('disables buttons when disabled prop is true', () => {
    render(
      <DndContext>
        <SortableContext items={[1]}>
          <ul>
            <BulletItem bullet={bullet} onUpdate={vi.fn()} onDelete={vi.fn()} disabled={true} />
          </ul>
        </SortableContext>
      </DndContext>
    );
    expect(screen.getByRole('button', { name: /edit/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /delete/i })).toBeDisabled();
  });
});
