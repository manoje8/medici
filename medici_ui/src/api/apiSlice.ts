import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import type { AuthStatus, HealthStatus, LoginResponse } from '@/types';
import { API_BASE_URL } from '@/utils/constants';

export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: API_BASE_URL,
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('medici_token');
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: (builder) => ({
    healthCheck: builder.query<HealthStatus, void>({
      query: () => '/health',
    }),

    authStatus: builder.query<AuthStatus, void>({
      query: () => '/auth-status',
    }),

    login: builder.mutation<LoginResponse, { username: string; password: string }>({
      query: (credentials) => {
        const formData = new URLSearchParams();
        formData.append('username', credentials.username);
        formData.append('password', credentials.password);
        return {
          url: '/login',
          method: 'POST',
          body: formData.toString(),
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        };
      },
    }),

    uploadDocument: builder.mutation<
      Record<string, unknown>,
      { file: File; parseMethod: string; docId: string }
    >({
      query: ({ file, parseMethod, docId }) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('parse_method', parseMethod);
        formData.append('doc_id', docId);
        return {
          url: '/ingestion',
          method: 'POST',
          body: formData,
        };
      },
    }),
  }),
});

export const {
  useHealthCheckQuery,
  useAuthStatusQuery,
  useLoginMutation,
  useUploadDocumentMutation,
} = apiSlice;
