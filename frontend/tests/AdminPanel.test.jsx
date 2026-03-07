import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AdminPanel } from '../src/components/admin/AdminPanel';
import { ThemeProvider } from '../src/hooks/useTheme';

vi.mock('../src/api', () => ({
  admin: {
    listUsers: vi.fn().mockResolvedValue([
      { id: 1, username: 'admin', role: 'admin', is_active: true, must_change_password: false, created_at: new Date().toISOString(), disabled_at: null },
    ]),
    getSettings: vi.fn().mockResolvedValue({ default_whisper_model: 'base', ollama_model: 'gpt-oss:20b' }),
  },
}));

vi.mock('../src/hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 1, username: 'admin', role: 'admin' }, logout: vi.fn() }),
  AuthProvider: ({ children }) => children,
}));

describe('AdminPanel', () => {
  it('renders users tab', async () => {
    render(
      <ThemeProvider>
        <MemoryRouter>
          <AdminPanel />
        </MemoryRouter>
      </ThemeProvider>
    );
    await waitFor(() => {
      expect(screen.getByText('Users')).toBeInTheDocument();
    });
  });

  it('shows user list after loading', async () => {
    render(
      <ThemeProvider>
        <MemoryRouter>
          <AdminPanel />
        </MemoryRouter>
      </ThemeProvider>
    );
    // The user table should render - verify the table header exists
    await waitFor(() => {
      expect(screen.getByRole('table', { name: /user list/i })).toBeInTheDocument();
    });
  });
});
