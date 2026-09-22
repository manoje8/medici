import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

import { useAppSelector } from '@/store/hooks';
import { truncateId } from '@/utils/formatters';

export function DebugPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const sessionId = useAppSelector((s) => s.chat.sessionId);
  const userId = useAppSelector((s) => s.chat.userId);
  const messageCount = useAppSelector((s) => s.chat.messages.length);
  const uploadedDocsCount = useAppSelector((s) => s.upload.uploadedDocs.length);

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs text-text-muted hover:text-text-secondary transition-colors w-full cursor-pointer"
      >
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform duration-200 ${isOpen ? 'rotate-0' : '-rotate-90'}`}
        />
        <span className="font-medium tracking-wide uppercase">Debug Info</span>
      </button>

      {isOpen && (
        <div className="mt-2 animate-[fade-in_0.2s_ease-out] bg-surface-800 rounded-lg p-3 text-xs font-mono space-y-1.5">
          <div className="flex justify-between">
            <span className="text-text-muted">session_id</span>
            <span className="text-primary-light">{truncateId(sessionId)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">user_id</span>
            <span className="text-primary-light">{truncateId(userId)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">messages</span>
            <span className="text-text-secondary">{messageCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">uploaded</span>
            <span className="text-text-secondary">{uploadedDocsCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">backend</span>
            <span className="text-text-secondary truncate ml-2">/api</span>
          </div>
        </div>
      )}
    </div>
  );
}
