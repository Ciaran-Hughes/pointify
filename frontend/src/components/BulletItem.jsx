import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { CheckIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useEffect, useRef, useState } from 'react';
import { bullets as bulletsApi } from '../api';

function BufferIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 31 36" fill="currentColor" aria-hidden="true">
      <path d="M1 9.34 15.17 2l14.322 7.34-14.322 7.366L1 9.34Z" />
      <path d="m5.503 15.787 9.667 4.754 9.769-4.754 4.553 2.218-14.322 6.973L1 18.005l4.503-2.218Z" />
      <path d="M15.17 29.301 5.503 24.06 1 26.493l14.17 7.676 14.322-7.676-4.553-2.434-9.77 5.242Z" />
    </svg>
  );
}

function Spinner({ className }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

export function BulletItem({ bullet, onUpdate, onDelete, onBufferSend, bufferEnabled, disabled }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(bullet.text);
  const [saving, setSaving] = useState(false);
  const [bufferSending, setBufferSending] = useState(false);
  const [bufferError, setBufferError] = useState(null);
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

  // Dismiss error when bullet text changes (e.g. user edited and re-saved)
  useEffect(() => {
    setText(bullet.text);
    setBufferError(null);
  }, [bullet.text]);

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

  const handleBufferSend = async () => {
    if (bufferSending || bullet.buffer_idea_id) return;
    setBufferSending(true);
    setBufferError(null);
    try {
      const result = await bulletsApi.addToBuffer(bullet.id);
      if (onBufferSend) onBufferSend(bullet.id, result.buffer_idea_id);
    } catch (err) {
      const msg = err.errorCode === 'BUFFER_ALREADY_SENT'
        ? 'Already in Buffer'
        : err.errorCode === 'BUFFER_UNAUTHORIZED'
          ? 'Buffer token invalid'
          : err.message || 'Failed to send to Buffer';
      setBufferError(msg);
    } finally {
      setBufferSending(false);
    }
  };

  const displayText =
    bullet.text.length > 0
      ? bullet.text.charAt(0).toUpperCase() + bullet.text.slice(1)
      : bullet.text;

  const alreadySent = Boolean(bullet.buffer_idea_id);

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

          {/* Buffer error inline */}
          {bufferError && (
            <span className="flex-shrink-0 text-xs text-red-500 dark:text-red-400 ml-1">{bufferError}</span>
          )}

          <div className="flex-shrink-0 flex items-center gap-1">
            {/* Buffer status: always-visible checkmark if sent; hover-only button if not sent and enabled */}
            {bufferEnabled && (
              alreadySent ? (
                <span
                  title="Sent to Buffer"
                  aria-label="Already sent to Buffer"
                  className="p-1 text-green-500 dark:text-green-400"
                >
                  <BufferIcon className="w-3.5 h-3.5" />
                </span>
              ) : (
                <button
                  onClick={handleBufferSend}
                  disabled={disabled || bufferSending}
                  aria-label={`Send to Buffer: ${bullet.text}`}
                  title="Add to Buffer"
                  className="p-1 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 rounded opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity disabled:opacity-40"
                >
                  {bufferSending
                    ? <Spinner className="w-3.5 h-3.5" />
                    : <BufferIcon className="w-3.5 h-3.5" />
                  }
                </button>
              )
            )}

            <div className="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
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
        </div>
      )}
    </li>
  );
}
