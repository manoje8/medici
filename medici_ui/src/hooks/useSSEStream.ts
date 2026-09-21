import { useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';

import {
  addMessage,
  addPipelineStage,
  appendStreamingToken,
  clearPipelineStages,
  clearStreamingTokens,
  setProcessing,
  setStreaming,
  updateLastAssistantMessage,
} from '@/features/chat/chatSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import type { SSEEvent } from '@/types';
import { parseAnswer } from '@/utils/citationParser';
import { API_BASE_URL, STAGE_ICONS } from '@/utils/constants';

/**
 * Custom hook to stream SSE events from the `/query/stream` endpoint.
 *
 * Uses `fetch()` + `ReadableStream` (not `EventSource`) because
 * the backend expects a `POST` body.
 */
export function useSSEStream() {
  const dispatch = useAppDispatch();
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = useAppSelector((s) => s.chat.sessionId);
  const userId = useAppSelector((s) => s.chat.userId);

  const startStream = useCallback(
    async (question: string) => {
      // Abort any in-flight stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      dispatch(setProcessing(true));
      dispatch(setStreaming(true));
      dispatch(clearPipelineStages());
      dispatch(clearStreamingTokens());

      // Add a placeholder assistant message
      const assistantMsgId = uuidv4();
      dispatch(
        addMessage({
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
        })
      );

      try {
        const token = localStorage.getItem('medici_token');
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE_URL}/query/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            question,
            session_id: sessionId,
            user_id: userId,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Backend error: ${response.status} ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE lines
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data:')) continue;

            const dataStr = trimmed.slice(5).trim();
            let event: SSEEvent;
            try {
              event = JSON.parse(dataStr);
            } catch {
              continue;
            }

            switch (event.type) {
              case 'progress': {
                const node = event.node ?? '';
                const icon = STAGE_ICONS[node] ?? '⚙️';
                dispatch(
                  addPipelineStage({
                    id: uuidv4(),
                    node,
                    message: event.message ?? '',
                    icon,
                    timestamp: Date.now(),
                  })
                );
                break;
              }

              case 'token': {
                dispatch(appendStreamingToken(event.content ?? ''));
                break;
              }

              case 'done': {
                const rawAnswer = event.answer ?? '';
                const { cleanText, citations, confidence, confidenceNote } =
                  parseAnswer(rawAnswer);

                dispatch(
                  updateLastAssistantMessage({
                    content: cleanText,
                    citations,
                    confidence: confidence ?? undefined,
                    confidenceNote: confidenceNote || undefined,
                    cacheHit: event.cache_hit ?? false,
                    sources: event.sources ?? [],
                  })
                );

                dispatch(setStreaming(false));
                dispatch(setProcessing(false));
                dispatch(clearStreamingTokens());
                return;
              }

              case 'error': {
                dispatch(
                  updateLastAssistantMessage({
                    content: `⚠️ ${event.message ?? 'An error occurred while processing your query.'}`,
                  })
                );
                dispatch(setStreaming(false));
                dispatch(setProcessing(false));
                dispatch(clearStreamingTokens());
                return;
              }
            }
          }
        }

        // If stream ended without a done event, finalize
        dispatch(setStreaming(false));
        dispatch(setProcessing(false));
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;

        dispatch(
          updateLastAssistantMessage({
            content: `⚠️ ${(err as Error).message || 'Connection error. Please try again.'}`,
          })
        );
        dispatch(setStreaming(false));
        dispatch(setProcessing(false));
        dispatch(clearStreamingTokens());
      }
    },
    [dispatch, sessionId, userId]
  );

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    dispatch(setStreaming(false));
    dispatch(setProcessing(false));
  }, [dispatch]);

  return { startStream, cancelStream };
}
