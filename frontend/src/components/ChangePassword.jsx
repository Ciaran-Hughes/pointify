import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth as authApi } from '../api';
import { useAuth } from '../hooks/useAuth';
import { PASSWORD_POLICY, validatePassword } from '../utils/validatePassword';

export function ChangePassword() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const policyErr = validatePassword(next);
    if (policyErr) { setError(policyErr); return; }
    if (next !== confirm) { setError('Passwords do not match'); return; }
    setLoading(true);
    try {
      await authApi.changePassword(current, next);
      await refreshUser();
      navigate('/');
    } catch (err) {
      setError(err.message || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Set New Password</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">You must change your password before continuing.</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 space-y-4">
          {error && (
            <div role="alert" className="bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-sm px-3 py-2 rounded-lg border border-red-200 dark:border-red-800">
              {error}
            </div>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400">{PASSWORD_POLICY}</p>
          {[
            { id: 'current', label: 'Current password', val: current, set: setCurrent, auto: 'current-password' },
            { id: 'new', label: 'New password', val: next, set: setNext, auto: 'new-password' },
            { id: 'confirm', label: 'Confirm new password', val: confirm, set: setConfirm, auto: 'new-password' },
          ].map(({ id, label, val, set, auto }) => (
            <div key={id}>
              <label htmlFor={id} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
              <input
                id={id}
                type="password"
                value={val}
                onChange={(e) => set(e.target.value)}
                required
                autoComplete={auto}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          ))}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {loading ? 'Saving…' : 'Set password'}
          </button>
        </form>
      </div>
    </div>
  );
}
