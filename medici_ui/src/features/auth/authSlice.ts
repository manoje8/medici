import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface AuthState {
  token: string | null;
  authMode: boolean;
  authConfigured: boolean | null;
  userName: string;
  role: string;
  status: 'idle' | 'checking' | 'authenticated' | 'unauthenticated';
}

const initialState: AuthState = {
  token: localStorage.getItem('medici_token'),
  authMode: false,
  authConfigured: null,
  userName: 'guest',
  role: 'guest',
  status: 'idle',
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setAuthChecking(state) {
      state.status = 'checking';
    },
    setAuthenticated(
      state,
      action: PayloadAction<{
        token: string;
        authMode: boolean;
        authConfigured: boolean;
        userName?: string;
        role?: string;
      }>
    ) {
      state.token = action.payload.token;
      state.authMode = action.payload.authMode;
      state.authConfigured = action.payload.authConfigured;
      state.userName = action.payload.userName ?? 'guest';
      state.role = action.payload.role ?? 'guest';
      state.status = 'authenticated';
      localStorage.setItem('medici_token', action.payload.token);
    },
    setUnauthenticated(state, action: PayloadAction<{ authConfigured: boolean }>) {
      state.token = null;
      state.authMode = true;
      state.authConfigured = action.payload.authConfigured;
      state.userName = '';
      state.role = '';
      state.status = 'unauthenticated';
      localStorage.removeItem('medici_token');
    },
    logout(state) {
      state.token = null;
      state.userName = '';
      state.role = '';
      state.status = 'unauthenticated';
      localStorage.removeItem('medici_token');
    },
  },
});

export const { setAuthChecking, setAuthenticated, setUnauthenticated, logout } =
  authSlice.actions;
export default authSlice.reducer;
