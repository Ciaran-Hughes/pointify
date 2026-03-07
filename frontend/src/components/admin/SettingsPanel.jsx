import { useCallback, useEffect, useState } from 'react';
import { admin as adminApi } from '../../api';

const WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v3'];

export function SettingsPanel() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSettings(await adminApi.getSettings());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const updated = await adminApi.updateSettings({
        default_whisper_model: settings.default_whisper_model,
      });
      setSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-400 py-6 text-center">Loading settings…</div>;

  return (
    <form onSubmit={handleSave} className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 space-y-5">
      <h2 className="text-base font-semibold text-gray-900 dark:text-white">System Settings</h2>

      {error && <p role="alert" className="text-red-600 dark:text-red-400 text-sm">{error}</p>}

      <div>
        <label htmlFor="whisper-default" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Default Whisper model
        </label>
        <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">Users can override this per recording.</p>
        <select
          id="whisper-default"
          value={settings.default_whisper_model}
          onChange={(e) => setSettings((s) => ({ ...s, default_whisper_model: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          {WHISPER_MODELS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Ollama model</p>
        <p className="text-sm text-gray-900 dark:text-white mt-1 font-mono">{settings.ollama_model}</p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Configured via OLLAMA_URL environment variable.</p>
      </div>

      <button
        type="submit"
        disabled={saving}
        className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
      >
        {saved ? 'Saved!' : saving ? 'Saving…' : 'Save settings'}
      </button>
    </form>
  );
}
