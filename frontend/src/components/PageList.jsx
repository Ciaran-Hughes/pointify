import { Cog6ToothIcon, DocumentTextIcon, PlusIcon } from '@heroicons/react/24/outline';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth as authApi, pages as pagesApi } from '../api';
import { useAuth } from '../hooks/useAuth';
import { ThemeToggle } from './ThemeToggle';

const WHISPER_LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'fi', label: 'Finnish' },
  { value: 'sv', label: 'Swedish' },
  { value: 'no', label: 'Norwegian' },
  { value: 'da', label: 'Danish' },
  { value: 'de', label: 'German' },
  { value: 'fr', label: 'French' },
  { value: 'es', label: 'Spanish' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'pl', label: 'Polish' },
  { value: 'ru', label: 'Russian' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'ar', label: 'Arabic' },
];

function UserPreferencesModal({ user, onClose, onSaved }) {
  const [language, setLanguage] = useState(user.whisper_language ?? 'en');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const updated = await authApi.updatePreferences({ whisper_language: language });
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4" role="dialog" aria-modal="true" aria-labelledby="prefs-title">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 w-full max-w-sm">
        <h2 id="prefs-title" className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Preferences</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p role="alert" className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
          <div>
            <label htmlFor="pref-language" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Default transcription language
            </label>
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">
              Used for all new recordings. You can override it per recording.
            </p>
            <select
              id="pref-language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {WHISPER_LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function NewPageModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    try {
      const page = await onCreate(name.trim());
      onClose(page);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4" role="dialog" aria-modal="true" aria-labelledby="new-page-title">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 w-full max-w-sm">
        <h2 id="new-page-title" className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">New page</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p role="alert" className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
          <div>
            <label htmlFor="page-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Page title</label>
            <input
              id="page-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              autoFocus
              required
              placeholder="e.g. Work Ideas, Daily Log…"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => onClose(null)} className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Cancel</button>
            <button type="submit" disabled={loading || !name.trim()} className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium transition-colors">
              {loading ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function PageList() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await pagesApi.list();
      setItems(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (name) => {
    return pagesApi.create(name);
  };

  const handleModalClose = (page) => {
    setShowModal(false);
    if (page) navigate(`/pages/${page.id}`);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">Pointify</h1>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setShowPrefs(true)}
            aria-label="Preferences"
            className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <Cog6ToothIcon className="w-5 h-5" aria-hidden="true" />
          </button>
          {user?.role === 'admin' && (
            <button onClick={() => navigate('/admin')} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline px-2 py-1">Admin</button>
          )}
          <button onClick={handleLogout} className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 px-2 py-1">Sign out</button>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <p className="text-gray-500 dark:text-gray-400 text-sm">{total} page{total !== 1 ? 's' : ''}</p>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Create new page"
          >
            <PlusIcon className="w-4 h-4" aria-hidden="true" />
            New page
          </button>
        </div>

        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-20 text-gray-500 dark:text-gray-400">
            <DocumentTextIcon className="w-12 h-12 mx-auto mb-3 opacity-40" aria-hidden="true" />
            <p className="font-medium">No pages yet</p>
            <p className="text-sm mt-1">Create your first page to start recording notes.</p>
          </div>
        )}

        <ul className="space-y-3" role="list">
          {items.map((page) => (
            <li key={page.id}>
              <button
                onClick={() => navigate(`/pages/${page.id}`)}
                className="w-full text-left bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl px-5 py-4 hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <p className="font-semibold text-gray-900 dark:text-white">{page.name}</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                  Updated {new Date(page.updated_at).toLocaleDateString(undefined, { dateStyle: 'medium' })}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </main>

      {showModal && <NewPageModal onCreate={handleCreate} onClose={handleModalClose} />}
      {showPrefs && user && (
        <UserPreferencesModal
          user={user}
          onClose={() => setShowPrefs(false)}
          onSaved={() => refreshUser()}
        />
      )}
    </div>
  );
}
