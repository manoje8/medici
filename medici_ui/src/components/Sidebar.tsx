import { Key, LayoutDashboard, LogOut, RefreshCw, Trash2 } from 'lucide-react';

import { Button } from '@/components/Button';
import { DebugPanel } from '@/components/DebugPanel';
import { clearMessages, resetSession } from '@/features/chat/chatSlice';
import { UploadPanel } from '@/features/upload/UploadPanel';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { truncateId } from '@/utils/formatters';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.chat.sessionId);
  const isProcessing = useAppSelector((s) => s.chat.isProcessing);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
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
        {/* Header */}
        <div className="p-5 border-b border-glass-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-glow">
              <LayoutDashboard className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-text-primary">Medici</h1>
              <p className="text-xs text-text-muted">Agentic Assistant</p>
            </div>
          </div>
        </div>

        {/* Session info */}
        <div className="px-5 pt-4 pb-2">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Key className="h-3.5 w-3.5" />
            <span>Session: {truncateId(sessionId)}</span>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-5">
          {/* Upload section */}
          <UploadPanel />

          {/* Divider */}
          <div className="border-t border-glass-border" />

          {/* Actions */}
          <div>
            <h3 className="text-xs font-semibold text-text-muted tracking-wider uppercase mb-3">
              ⚙️ Actions
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                disabled={isProcessing}
                onClick={() => dispatch(clearMessages())}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear
              </Button>
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                disabled={isProcessing}
                onClick={() => dispatch(resetSession())}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                New
              </Button>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-glass-border" />

          {/* Debug panel */}
          <DebugPanel />
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-glass-border">
          <Button
            variant="ghost"
            size="sm"
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
