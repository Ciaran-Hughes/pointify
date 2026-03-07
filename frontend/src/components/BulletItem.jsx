import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { CheckIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useEffect, useRef, useState } from 'react';

export function BulletItem({ bullet, onUpdate, onDelete, disabled }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(bullet.text);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: bullet.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleSave = async () => {
    if (!text.trim() || text === bullet.text) { setEditing(false); return; }
    setSaving(true);
    try {
      await onUpdate(bullet.id, text.trim());
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSave();
    if (e.key === 'Escape') { setText(bullet.text); setEditing(false); }
  };

  const displayText =
    bullet.text.length > 0
      ? bullet.text.charAt(0).toUpperCase() + bullet.text.slice(1)
      : bullet.text;

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 group py-1 min-h-[1.5rem]"
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        disabled={disabled}
        className="flex-shrink-0 cursor-grab active:cursor-grabbing text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 rounded p-0.5 -m-0.5"
        tabIndex={0}
      >
        <svg className="w-4 h-4 block" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path d="M7 3a1 1 0 000 2h6a1 1 0 000-2H7zm-1 4a1 1 0 000 2h8a1 1 0 000-2H6zm-1 4a1 1 0 000 2h10a1 1 0 000-2H5z" />
        </svg>
      </button>

      <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-indigo-500 dark:bg-indigo-400" aria-hidden="true" />

      {editing ? (
        <div className="flex-1 flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={2000}
            aria-label="Edit bullet text"
            className="flex-1 text-sm bg-transparent border-b border-indigo-400 focus:outline-none text-gray-900 dark:text-white py-0.5"
          />
          <button
            onClick={handleSave}
            disabled={saving}
            aria-label="Save"
            className="text-green-600 dark:text-green-400 hover:text-green-700 focus:outline-none focus:ring-1 focus:ring-green-400 rounded"
          >
            <CheckIcon className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="flex-1 flex items-center gap-1 min-w-0">
          <span className="flex-1 text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{displayText}</span>
          <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
            <button
              onClick={() => setEditing(true)}
              disabled={disabled}
              aria-label={`Edit: ${bullet.text}`}
              className="p-1 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 rounded"
            >
              <PencilIcon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onDelete(bullet.id)}
              disabled={disabled}
              aria-label={`Delete: ${bullet.text}`}
              className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 focus:outline-none focus:ring-1 focus:ring-red-400 rounded"
            >
              <TrashIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
