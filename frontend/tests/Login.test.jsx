import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { Login } from '../src/components/Login';
import { AuthProvider } from '../src/hooks/useAuth';
import { ThemeProvider } from '../src/hooks/useTheme';

vi.mock('../src/api', () => ({
  auth: { login: vi.fn(), me: vi.fn() },
  storeLoginResponse: vi.fn(),
  clearTokens: vi.fn(),
}));

import { auth as authApi, storeLoginResponse } from '../src/api';

function renderLogin() {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

describe('Login', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders login form', () => {
    renderLogin();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows error on failed login', async () => {
    authApi.login.mockRejectedValue(new Error('Invalid credentials'));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/username/i), 'bad');
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong');
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('disables button while loading', async () => {
    authApi.login.mockImplementation(() => new Promise(() => {}));
    renderLogin();
    await userEvent.type(screen.getByLabelText(/username/i), 'admin');
    await userEvent.type(screen.getByLabelText(/password/i), 'Admin123!');
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();
    });
  });
});
