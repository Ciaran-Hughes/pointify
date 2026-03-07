import { Cog6ToothIcon, UsersIcon } from '@heroicons/react/24/outline';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ThemeToggle } from '../ThemeToggle';
import { SettingsPanel } from './SettingsPanel';
import { UserList } from './UserList';

export function AdminPanel() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('users');

  const tabs = [
    { id: 'users', label: 'Users', Icon: UsersIcon },
    { id: 'settings', label: 'Settings', Icon: Cog6ToothIcon },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline focus:outline-none">← Back</button>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">Admin Panel</h1>
        </div>
        <ThemeToggle />
      </header>

      <div className="max-w-3xl mx-auto px-4 py-6">
        <nav className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-800 p-1 rounded-xl" aria-label="Admin sections">
          {tabs.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              aria-current={tab === id ? 'page' : undefined}
              className={`flex items-center gap-2 flex-1 justify-center py-2 px-3 rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500
                ${tab === id ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}
              `}
            >
              <Icon className="w-4 h-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>

        {tab === 'users' && <UserList />}
        {tab === 'settings' && <SettingsPanel />}
      </div>
    </div>
  );
}
