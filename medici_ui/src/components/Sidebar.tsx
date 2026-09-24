import { Clock, Key, LogOut, MessageSquare, Trash2 } from 'lucide-react';
import { useCallback } from 'react';

import { useLazyGetSessionHistoryQuery, useListSessionsQuery, useDeleteSessionMutation } from '@/api/apiSlice';
import { Button } from '@/components/Button';
import { DebugPanel } from '@/components/DebugPanel';
import { loadSession, resetSession } from '@/features/chat/chatSlice';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { truncateId } from '@/utils/formatters';
import { Icon } from '@iconify/react';

import type { Message } from '@/types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

function formatRelativeDate(isoStr: string): string {
  const date = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.chat.sessionId);
  const userId = useAppSelector((s) => s.chat.userId);
  const isProcessing = useAppSelector((s) => s.chat.isProcessing);

  const { data: sessionsData, refetch } = useListSessionsQuery(
    { userId },
    { pollingInterval: 30_000 }
  );
  const [fetchHistory] = useLazyGetSessionHistoryQuery();
  const [deleteSession] = useDeleteSessionMutation();

  const sessions = sessionsData?.sessions ?? [];

  const handleLoadSession = useCallback(
    async (targetSessionId: string) => {
      if (targetSessionId === sessionId) return;
      try {
        const result = await fetchHistory(targetSessionId).unwrap();
        const messages: Message[] = result.turns.map((turn, idx) => ({
          id: `${targetSessionId}-${idx}`,
          role: turn.role as 'user' | 'assistant',
          content: turn.content,
          timestamp: new Date(turn.created_at).getTime(),
        }));
        dispatch(loadSession({ sessionId: targetSessionId, messages }));
        onClose();
      } catch {
        // silently ignore — user can retry
      }
    },
    [sessionId, fetchHistory, dispatch, onClose]
  );

  const handleDelete = useCallback(
    async (e: React.MouseEvent, targetSessionId: string) => {
      e.stopPropagation();
      await deleteSession(targetSessionId);
      if (targetSessionId === sessionId) {
        dispatch(resetSession());
      }
      refetch();
    },
    [deleteSession, sessionId, dispatch, refetch]
  );

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-surface-600 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed lg:relative inset-y-0 left-0 z-50
          w-80 flex flex-col
          glass-strong
          border-r border-glass-border
          transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >

        <div className="p-5 border-b border-glass-border">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-lg font-bold text-text-primary">Medici</h1>
            </div>
          </div>
        </div>

        <button
          className="m-1 flex items-center gap-2 px-5 py-3 text-sm font-semibold text-text-primary hover:bg-surface-700 transition-colors rounded-sm"
          disabled={isProcessing}
          onClick={() => dispatch(resetSession())}
        >
          <Icon icon="codex:plus" height={20} width={20}/>
          New
        </button>

        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.length > 0 && (
            <div className="space-y-0.5">
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => handleLoadSession(s.session_id)}
                  className={`
                    group w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left
                    transition-colors text-sm cursor-pointer
                    ${s.session_id === sessionId
                      ? 'bg-surface-700 text-text-primary'
                      : 'text-text-secondary hover:bg-surface-800 hover:text-text-primary'
                    }
                  `}
                >
                  <MessageSquare className="h-3.5 w-3.5 flex-shrink-0 opacity-50" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{s.title}</div>
                    <div className="flex items-center gap-1 mt-0.5 text-xs text-text-muted">
                      <Clock className="h-2.5 w-2.5" />
                      {formatRelativeDate(s.updated_at)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, s.session_id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 hover:text-red-400 transition-all"
                    title="Delete session"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="px-5 pt-4 pb-2">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Key className="h-3.5 w-3.5" />
            <span>Session: {truncateId(sessionId)}</span>
          </div>
        </div>

        <div className="px-5 pb-4 space-y-5">
          <div className="border-t border-glass-border" />
          <DebugPanel />
        </div>

        <div className="p-4 border-t border-glass-border">
          <Button
            variant="ghost"
            size="lg"
            fullWidth
            onClick={() => {
              localStorage.removeItem('medici_token');
              window.location.reload();
            }}
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </Button>
        </div>
      </aside>
    </>
  );
}
