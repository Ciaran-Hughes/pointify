import { useState } from 'react';
import { PASSWORD_POLICY, validatePassword } from '../../utils/validatePassword';

export function UserForm({ title, onSubmit, onClose, showRole = false, passwordOnly = false }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const pwErr = validatePassword(password);
    if (pwErr) { setError(pwErr); return; }
    setLoading(true);
    try {
      await onSubmit({ username, password, role });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4" role="dialog" aria-modal="true" aria-labelledby="user-form-title">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 w-full max-w-sm space-y-4">
        <h2 id="user-form-title" className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <p role="alert" className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
          <p className="text-xs text-gray-400">{PASSWORD_POLICY}</p>

          {!passwordOnly && (
            <div>
              <label htmlFor="uf-username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
              <input
                id="uf-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                pattern="[a-zA-Z0-9_]{3,30}"
                title="3-30 characters, letters, digits, underscores"
                autoFocus
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          <div>
            <label htmlFor="uf-password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {passwordOnly ? 'New password' : 'Password'}
            </label>
            <input
              id="uf-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus={passwordOnly}
              autoComplete="new-password"
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {showRole && (
            <div>
              <label htmlFor="uf-role" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
              <select
                id="uf-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {loading ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
