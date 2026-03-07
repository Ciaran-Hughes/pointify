import { useState } from 'react';

export function TranscriptView({ transcript }) {
  const [open, setOpen] = useState(false);
  if (!transcript) return null;

  return (
    <div className="mt-2 text-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors text-xs font-medium"
      >
        <span className="transition-transform" style={{ display: 'inline-block', transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
        {open ? 'Hide transcript' : 'Show transcript'}
      </button>
      {open && (
        <p className="mt-2 text-gray-500 dark:text-gray-400 leading-relaxed bg-gray-50 dark:bg-gray-700/50 rounded-lg px-3 py-2 italic text-xs">
          {transcript}
        </p>
      )}
    </div>
  );
}
