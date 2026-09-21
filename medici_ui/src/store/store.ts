import { configureStore } from '@reduxjs/toolkit';

import { apiSlice } from '@/api/apiSlice';
import authReducer from '@/features/auth/authSlice';
import chatReducer from '@/features/chat/chatSlice';
import uploadReducer from '@/features/upload/uploadSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    chat: chatReducer,
    upload: uploadReducer,
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(apiSlice.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
