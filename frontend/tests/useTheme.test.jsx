import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ThemeProvider, useTheme } from '../src/hooks/useTheme';

function Tester() {
  const { theme, toggle } = useTheme();
  return (
    <div>
      <span data-testid="theme-value">{theme}</span>
      <button onClick={toggle} aria-label="Toggle theme">Toggle</button>
    </div>
  );
}

describe('useTheme / ThemeProvider', () => {
  const getStoredTheme = () => localStorage.getItem('theme');

  beforeEach(() => {
    document.documentElement.classList.remove('dark');
    localStorage.clear();
  });

  it('applies dark class to document when theme is dark', () => {
    localStorage.setItem('theme', 'dark');
    render(
      <ThemeProvider>
        <Tester />
      </ThemeProvider>
    );
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(getStoredTheme()).toBe('dark');
  });

  it('removes dark class when theme is light', () => {
    localStorage.setItem('theme', 'light');
    render(
      <ThemeProvider>
        <Tester />
      </ThemeProvider>
    );
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(getStoredTheme()).toBe('light');
  });

  it('toggle switches theme and updates document and localStorage', async () => {
    localStorage.setItem('theme', 'light');
    render(
      <ThemeProvider>
        <Tester />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: /toggle theme/i }));
    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(getStoredTheme()).toBe('dark');

    await userEvent.click(screen.getByRole('button', { name: /toggle theme/i }));
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(getStoredTheme()).toBe('light');
  });

  it('useTheme throws when used outside ThemeProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Tester />)).toThrow('useTheme must be used within ThemeProvider');
    consoleSpy.mockRestore();
  });
});
