import { Menu } from 'lucide-react';
import { useState } from 'react';

import { HealthBanner } from '@/components/HealthBanner';
import { Sidebar } from '@/components/Sidebar';
import { ChatInput } from '@/features/chat/ChatInput';
import { MessageList } from '@/features/chat/MessageList';
import { StreamingAnswer } from '@/features/chat/StreamingAnswer';
import { useHealthCheck } from '@/hooks/useHealthCheck';
import { useAppSelector } from '@/store/hooks';

export function ChatPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isHealthy } = useHealthCheck();
  const isStreaming = useAppSelector((s) => s.chat.isStreaming);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col min-w-0">
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-glass-border glass">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
            aria-label="Open sidebar"
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-semibold text-text-primary">Medici</h1>
        </div>

        <HealthBanner isHealthy={isHealthy} />

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto w-full">
            <MessageList />
            {isStreaming && <StreamingAnswer />}
          </div>
        </div>

        <div className="border-t border-glass-border bg-surface-900 backdrop-blur-sm">
          <div className="max-w-5xl mx-auto w-full">
            <ChatInput />
          </div>
        </div>
      </main>
    </div>
  );
}
