import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { ArrowPathIcon, ArchiveBoxXMarkIcon, PlusIcon } from '@heroicons/react/24/outline';
import { useState } from 'react';
import { bullets as bulletsApi, recordings as recordingsApi } from '../api';
import { BulletItem } from './BulletItem';
import { TranscriptView } from './TranscriptView';

function RecordingSection({ recording, initialBullets, pageId, onArchive, onBulletsChange }) {
  const [bulletList, setBulletList] = useState(initialBullets);
  const [retranscribing, setRetranscribing] = useState(false);
  const [busy, setBusy] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = async ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIdx = bulletList.findIndex((b) => b.id === active.id);
    const newIdx = bulletList.findIndex((b) => b.id === over.id);
    const reordered = [...bulletList];
    const [moved] = reordered.splice(oldIdx, 1);
    reordered.splice(newIdx, 0, moved);
    setBulletList(reordered);
    await bulletsApi.reorder(pageId, reordered.map((b) => b.id));
  };

  const handleUpdate = async (id, text) => {
    const updated = await bulletsApi.update(id, text);
    setBulletList((prev) => prev.map((b) => (b.id === id ? updated : b)));
  };

  const handleDelete = async (id) => {
    setBusy(true);
    try {
      await bulletsApi.delete(id);
      setBulletList((prev) => prev.filter((b) => b.id !== id));
    } finally {
      setBusy(false);
    }
  };

  const handleRetranscribe = async () => {
    setRetranscribing(true);
    try {
      await recordingsApi.retranscribe(recording.id);
      onBulletsChange();
    } finally {
      setRetranscribing(false);
    }
  };

  const handleArchive = async () => {
    await recordingsApi.archive(recording.id);
    onArchive(recording.id);
  };

  const time = new Date(recording.created_at).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden mb-3 last:mb-0">
      {/* Recording sub-header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-700/40 border-b border-gray-100 dark:border-gray-700">
        <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">{time}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={handleRetranscribe}
            disabled={retranscribing}
            aria-label="Re-transcribe and re-generate bullet points"
            title="Retranscribe audio"
            className="p-1.5 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-lg transition-colors focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-40"
          >
            <ArrowPathIcon className={`w-4 h-4 ${retranscribing ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleArchive}
            aria-label="Archive this recording"
            title="Archive recording"
            className="p-1.5 text-gray-400 hover:text-amber-600 dark:hover:text-amber-400 rounded-lg transition-colors focus:outline-none focus:ring-1 focus:ring-amber-400"
          >
            <ArchiveBoxXMarkIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Transcript (collapsible) */}
      {recording.transcript && (
        <div className="px-4 pt-3">
          <TranscriptView transcript={recording.transcript} />
        </div>
      )}

      {/* Bullet points */}
      <div className="px-4 py-3">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={bulletList.map((b) => b.id)} strategy={verticalListSortingStrategy}>
            <ul className="space-y-0.5" aria-label="Bullet points">
              {bulletList.map((bullet) => (
                <BulletItem
                  key={bullet.id}
                  bullet={bullet}
                  onUpdate={handleUpdate}
                  onDelete={handleDelete}
                  disabled={busy}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
        {bulletList.length === 0 && (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">No bullet points yet.</p>
        )}
      </div>
    </div>
  );
}

export function DayGroup({ group, pageId, onDelete, onUpdate }) {
  const { day, groups, orphan_bullets: initialOrphanBullets } = group;
  const [orphanBullets, setOrphanBullets] = useState(initialOrphanBullets);
  const [addingText, setAddingText] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState(false);

  const label = new Date(day + 'T12:00:00').toLocaleDateString(undefined, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleOrphanDragEnd = async ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIdx = orphanBullets.findIndex((b) => b.id === active.id);
    const newIdx = orphanBullets.findIndex((b) => b.id === over.id);
    const reordered = [...orphanBullets];
    const [moved] = reordered.splice(oldIdx, 1);
    reordered.splice(newIdx, 0, moved);
    setOrphanBullets(reordered);
    await bulletsApi.reorder(pageId, reordered.map((b) => b.id));
  };

  const handleOrphanUpdate = async (id, text) => {
    const updated = await bulletsApi.update(id, text);
    setOrphanBullets((prev) => prev.map((b) => (b.id === id ? updated : b)));
  };

  const handleOrphanDelete = async (id) => {
    setBusy(true);
    try {
      await bulletsApi.delete(id);
      setOrphanBullets((prev) => prev.filter((b) => b.id !== id));
    } finally {
      setBusy(false);
    }
  };

  const handleAddBullet = async (e) => {
    e.preventDefault();
    if (!addingText.trim()) return;
    setBusy(true);
    try {
      const bp = await bulletsApi.add(pageId, addingText.trim(), day);
      setOrphanBullets((prev) => [...prev, bp]);
      setAddingText('');
      setShowAdd(false);
    } finally {
      setBusy(false);
    }
  };

  const handleRecordingArchived = (recordingId) => {
    // If all recordings on this day are gone, remove the day entirely
    const remaining = groups.filter((g) => g.recording.id !== recordingId);
    if (remaining.length === 0 && orphanBullets.length === 0) {
      onDelete(day);
    } else {
      onUpdate();
    }
  };

  return (
    <section aria-labelledby={`day-${day}`} className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Day header */}
      <div className="px-5 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
        <h2 id={`day-${day}`} className="font-semibold text-sm text-gray-700 dark:text-gray-300">{label}</h2>
      </div>

      {/* Per-recording sections */}
      <div className="px-5 pt-4">
        {groups.map(({ recording, bullets }) => (
          <RecordingSection
            key={recording.id}
            recording={recording}
            initialBullets={bullets}
            pageId={pageId}
            onArchive={handleRecordingArchived}
            onBulletsChange={onUpdate}
          />
        ))}

        {/* Orphan (manually added) bullets */}
        {(orphanBullets.length > 0 || showAdd) && (
          <div className="mt-1">
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleOrphanDragEnd}>
              <SortableContext items={orphanBullets.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                <ul className="space-y-0.5" aria-label="Manual bullet points">
                  {orphanBullets.map((bullet) => (
                    <BulletItem
                      key={bullet.id}
                      bullet={bullet}
                      onUpdate={handleOrphanUpdate}
                      onDelete={handleOrphanDelete}
                      disabled={busy}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          </div>
        )}

        {/* Add bullet */}
        <div className="pb-4 mt-2">
          {showAdd ? (
            <form onSubmit={handleAddBullet} className="flex gap-2">
              <input
                type="text"
                value={addingText}
                onChange={(e) => setAddingText(e.target.value)}
                placeholder="Add a note…"
                maxLength={2000}
                autoFocus
                aria-label="New bullet point text"
                className="flex-1 text-sm border-b border-gray-300 dark:border-gray-600 bg-transparent focus:outline-none focus:border-indigo-500 text-gray-900 dark:text-white py-1"
              />
              <button type="submit" disabled={!addingText.trim() || busy} className="text-xs text-indigo-600 dark:text-indigo-400 font-medium hover:underline focus:outline-none">Add</button>
              <button type="button" onClick={() => setShowAdd(false)} className="text-xs text-gray-400 hover:underline focus:outline-none">Cancel</button>
            </form>
          ) : (
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors focus:outline-none focus:ring-1 focus:ring-indigo-400 rounded"
            >
              <PlusIcon className="w-3.5 h-3.5" aria-hidden="true" />
              Add bullet
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
