import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { AUTH_REQUIRED_EVENT, authApi } from '../services/authApi';
import { LoginModal } from './LoginModal';

type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

export const RequireAuth = ({ children }: { children: ReactNode }) => {
  const navigate = useNavigate();
  const [state, setState] = useState<AuthState>('checking');

  const check = useCallback(async () => {
    setState((await authApi.ensureSession()) ? 'authenticated' : 'unauthenticated');
  }, []);

  useEffect(() => {
    void check();
    const onAuthRequired = () => { void check(); };
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, [check]);

  if (state === 'checking') {
    return null;
  }

  if (state === 'unauthenticated') {
    return (
      <LoginModal
        isOpen
        onSuccess={() => setState('authenticated')}
        onClose={() => navigate('/')}
      />
    );
  }

  return <>{children}</>;
};
