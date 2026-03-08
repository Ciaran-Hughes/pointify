import { ArrowLeftIcon, MicrophoneIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { pages as pagesApi } from '../api';
import { ThemeToggle } from './ThemeToggle';
import { DayGroup } from './DayGroup';
import { VoiceRecorder } from './VoiceRecorder';

export function PageView() {
  const { pageId } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(null);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showRecorder, setShowRecorder] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [newName, setNewName] = useState('');
  const [deleting, setDeleting] = useState(false);
  const nameInputRef = useRef(null);

  const loadPage = useCallback(async () => {
    setLoading(true);
    try {
      const [pageData, daysData] = await Promise.all([
        pagesApi.get(pageId),
        pagesApi.days(pageId),
      ]);
      setPage(pageData);
      setNewName(pageData.name);
      setGroups(daysData);
    } finally {
      setLoading(false);
    }
  }, [pageId]);

  useEffect(() => { loadPage(); }, [loadPage]);

  useEffect(() => {
    if (editingName && nameInputRef.current) nameInputRef.current.focus();
  }, [editingName]);

  const handleSaveName = async () => {
    if (!newName.trim() || newName === page.name) { setEditingName(false); return; }
    const updated = await pagesApi.update(pageId, newName.trim());
    setPage(updated);
    setEditingName(false);
  };

  const handleRecordingComplete = () => {
    setShowRecorder(false);
    loadPage();
  };

  const handleDayDelete = (day) => {
    setGroups((prev) => prev.filter((g) => g.day !== day));
  };

  const handleDeletePage = async () => {
    if (!window.confirm('Delete this page? All recordings and notes will be removed.')) return;
    setDeleting(true);
    try {
      await pagesApi.delete(pageId);
      navigate('/');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
      <div className="text-gray-400 dark:text-gray-500">Loading…</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 pb-24">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center gap-3 sticky top-0 z-10">
        <button
          onClick={() => navigate('/')}
          aria-label="Back to pages"
          className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <ArrowLeftIcon className="w-5 h-5" />
        </button>

        <div className="flex-1 min-w-0">
          {editingName ? (
            <input
              ref={nameInputRef}
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onBlur={handleSaveName}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') setEditingName(false); }}
              maxLength={100}
              aria-label="Page name"
              className="w-full text-lg font-bold bg-transparent border-b-2 border-indigo-500 focus:outline-none text-gray-900 dark:text-white"
            />
          ) : (
            <button
              onClick={() => setEditingName(true)}
              className="flex items-center gap-1.5 group focus:outline-none"
              aria-label={`Page name: ${page?.name}. Click to edit.`}
            >
              <span className="text-lg font-bold text-gray-900 dark:text-white truncate">{page?.name}</span>
              <PencilIcon className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 group-focus:opacity-100 transition-opacity flex-shrink-0" aria-hidden="true" />
            </button>
          )}
        </div>

        <button
          onClick={handleDeletePage}
          disabled={deleting}
          aria-label="Delete page"
          className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:pointer-events-none"
        >
          <TrashIcon className="w-5 h-5" />
        </button>
        <ThemeToggle />
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-4">
        {showRecorder && (
          <VoiceRecorder pageId={pageId} onRecordingComplete={handleRecordingComplete} />
        )}

        {groups.length === 0 && (
          <div className="text-center py-20 text-gray-400 dark:text-gray-500">
            <MicrophoneIcon className="w-12 h-12 mx-auto mb-3 opacity-40" aria-hidden="true" />
            <p className="font-medium">No recordings yet</p>
            <p className="text-sm mt-1">Tap the microphone to record your first voice note.</p>
          </div>
        )}

        {groups.map((group) => (
          <DayGroup
            key={group.day}
            group={group}
            pageId={pageId}
            onDelete={handleDayDelete}
            onUpdate={loadPage}
          />
        ))}
      </main>

      {/* Microphone FAB */}
      <div className="fixed bottom-6 right-6 z-20">
        <button
          onClick={() => setShowRecorder((s) => !s)}
          aria-label={showRecorder ? 'Hide recorder' : 'Open voice recorder'}
          aria-expanded={showRecorder}
          className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500
            ${showRecorder ? 'bg-gray-700 dark:bg-gray-600 hover:bg-gray-800' : 'bg-indigo-600 hover:bg-indigo-700'}
          `}
        >
          <MicrophoneIcon className="w-6 h-6 text-white" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
