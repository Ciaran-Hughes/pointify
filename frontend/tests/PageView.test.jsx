import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';
import { ThemeProvider } from '../src/hooks/useTheme';
import { PageView } from '../src/components/PageView';

const PAGE_ID = '00000000-0000-0000-0000-000000000001';

const mockGet = vi.fn();
const mockDays = vi.fn();
const mockDelete = vi.fn();

vi.mock('../src/api', () => ({
  pages: {
    get: (...args) => mockGet(...args),
    days: (...args) => mockDays(...args),
    delete: (...args) => mockDelete(...args),
  },
}));

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderPageView() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[`/pages/${PAGE_ID}`]}>
        <Routes>
          <Route path="/pages/:pageId" element={<PageView />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe('PageView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({
      id: PAGE_ID,
      name: 'Test Page',
      updated_at: new Date().toISOString(),
    });
    mockDays.mockResolvedValue([]);
    vi.stubGlobal('confirm', vi.fn());
  });

  it('shows delete page button with accessible label', async () => {
    renderPageView();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete page/i })).toBeInTheDocument();
    });
  });

  it('calls pages.delete and navigate when user confirms delete', async () => {
    window.confirm.mockReturnValue(true);
    mockDelete.mockResolvedValue(null);

    renderPageView();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete page/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete page/i }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith(
        'Delete this page? All recordings and notes will be removed.'
      );
    });
    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith(PAGE_ID);
    });
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('does not call pages.delete when user cancels confirm', async () => {
    window.confirm.mockReturnValue(false);

    renderPageView();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete page/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /delete page/i }));

    expect(window.confirm).toHaveBeenCalledWith(
      'Delete this page? All recordings and notes will be removed.'
    );
    expect(mockDelete).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('disables delete button while deleting', async () => {
    window.confirm.mockReturnValue(true);
    mockDelete.mockImplementation(() => new Promise(() => {}));

    renderPageView();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /delete page/i })).toBeInTheDocument();
    });

    const deleteBtn = screen.getByRole('button', { name: /delete page/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deleteBtn).toBeDisabled();
    });
  });
});
