import { useEffect } from 'react';

import { useAuthStatusQuery } from '@/api/apiSlice';
import { Spinner } from '@/components/Spinner';
import {
  setAuthenticated,
  setAuthChecking,
  setUnauthenticated,
} from '@/features/auth/authSlice';
import { LoginPage } from '@/features/auth/LoginPage';
import { useAppDispatch, useAppSelector } from '@/store/hooks';

interface AuthGateProps {
  children: React.ReactNode;
}

/**
 * Wraps the main app. On mount, calls GET /auth-status:
 *   - If auth disabled → stores guest token, renders children
 *   - If auth enabled → renders LoginPage
 */
export function AuthGate({ children }: AuthGateProps) {
  const dispatch = useAppDispatch();
  const authStatus = useAppSelector((s) => s.auth.status);
  const { data, isLoading, error } = useAuthStatusQuery();

  useEffect(() => {
    dispatch(setAuthChecking());
  }, [dispatch]);

  useEffect(() => {
    if (!data) return;

    if (!data.auth_configured && data.access_token) {
      // Guest mode — auth disabled
      dispatch(
        setAuthenticated({
          token: data.access_token,
          authMode: false,
          authConfigured: false,
          userName: 'guest',
          role: 'guest',
        })
      );
    } else if (data.auth_configured) {
      const storedToken = localStorage.getItem('medici_token');
      if (storedToken) {
        dispatch(
          setAuthenticated({
            token: storedToken,
            authMode: true,
            authConfigured: true,
          })
        );
      } else {
        dispatch(setUnauthenticated({ authConfigured: true }));
      }
    }
  }, [data, dispatch]);

  if (isLoading || authStatus === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-900">
        <div className="flex flex-col items-center gap-4 animate-[fade-in_0.3s_ease-out]">
          <Spinner size="md" />
          <p className="text-sm text-text-muted">Connecting to Medici…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return <>{children}</>;
  }

  if (authStatus === 'unauthenticated') {
    return <LoginPage />;
  }

  return <>{children}</>;
}
