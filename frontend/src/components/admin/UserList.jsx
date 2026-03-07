import { useCallback, useEffect, useState } from 'react';
import { admin as adminApi } from '../../api';
import { useAuth } from '../../hooks/useAuth';
import { UserForm } from './UserForm';

function UserRow({ user, onAction, currentUserId }) {
  const isSelf = user.id === currentUserId;
  return (
    <tr className="border-t border-gray-100 dark:border-gray-700">
      <td className="px-4 py-3 text-sm text-gray-900 dark:text-white font-medium">
        {user.username}
        {isSelf && <span className="ml-1 text-xs text-indigo-500">(you)</span>}
      </td>
      <td className="px-4 py-3 text-sm">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
          ${user.role === 'admin' ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`}>
          {user.role}
        </span>
      </td>
      <td className="px-4 py-3 text-sm">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
          ${user.is_active ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'}`}>
          {user.is_active ? 'Active' : 'Disabled'}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex gap-2 justify-end flex-wrap">
          <button onClick={() => onAction('reset', user)} className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline focus:outline-none">Reset pw</button>
          {!isSelf && user.is_active && (
            <button onClick={() => onAction('disable', user)} className="text-xs text-red-500 hover:underline focus:outline-none">Disable</button>
          )}
          {!user.is_active && (
            <button onClick={() => onAction('enable', user)} className="text-xs text-green-600 dark:text-green-400 hover:underline focus:outline-none">Enable</button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function UserList() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await adminApi.listUsers());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (action, user) => {
    setError('');
    try {
      if (action === 'disable') {
        if (!window.confirm(`Disable ${user.username}?`)) return;
        await adminApi.disableUser(user.id);
      } else if (action === 'enable') {
        await adminApi.enableUser(user.id);
      } else if (action === 'reset') {
        setResetTarget(user);
        return;
      }
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleResetPassword = async (newPassword) => {
    await adminApi.resetPassword(resetTarget.id, newPassword);
    setResetTarget(null);
    await load();
  };

  if (loading) return <div className="text-gray-400 py-6 text-center">Loading users…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">Users ({users.length})</h2>
        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-3 py-1.5 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          + New user
        </button>
      </div>

      {error && <p role="alert" className="text-red-600 dark:text-red-400 text-sm">{error}</p>}

      <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full" aria-label="User list">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/50 text-left">
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Username</th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Role</th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <UserRow key={u.id} user={u} onAction={handleAction} currentUserId={currentUser?.id} />
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <UserForm
          title="Create new user"
          onSubmit={async (data) => { await adminApi.createUser(data); await load(); setShowForm(false); }}
          onClose={() => setShowForm(false)}
          showRole
        />
      )}

      {resetTarget && (
        <UserForm
          title={`Reset password for ${resetTarget.username}`}
          onSubmit={async ({ password }) => { await handleResetPassword(password); }}
          onClose={() => setResetTarget(null)}
          passwordOnly
        />
      )}
    </div>
  );
}
