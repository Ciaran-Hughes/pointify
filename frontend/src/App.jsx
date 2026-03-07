import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { AdminPanel } from './components/admin/AdminPanel';
import { ChangePassword } from './components/ChangePassword';
import { Login } from './components/Login';
import { PageList } from './components/PageList';
import { PageView } from './components/PageView';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ThemeProvider } from './hooks/useTheme';

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500 dark:text-gray-400">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  return children;
}

function RequireAdmin({ children }) {
  const { user } = useAuth();
  if (!user || user.role !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function AuthListener() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  useEffect(() => {
    const handler = () => { logout(); navigate('/login'); };
    window.addEventListener('auth:expired', handler);
    return () => window.removeEventListener('auth:expired', handler);
  }, [logout, navigate]);
  return null;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AuthListener />
          <div className="min-h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/change-password" element={<ChangePassword />} />
              <Route path="/" element={<RequireAuth><PageList /></RequireAuth>} />
              <Route path="/pages/:pageId" element={<RequireAuth><PageView /></RequireAuth>} />
              <Route path="/admin" element={<RequireAuth><RequireAdmin><AdminPanel /></RequireAdmin></RequireAuth>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
