import { clsx } from 'clsx';
import { Bot, User } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { CacheBadge } from '@/features/chat/CacheBadge';
import { ConfidenceBadge } from '@/features/chat/ConfidenceBadge';
import { SourceCard } from '@/features/chat/SourceCard';
import type { Message } from '@/types';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={clsx(
        'flex gap-3 py-4 animate-[fade-in_0.3s_ease-out]',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      {!isUser && (
        <div className="shrink-0 mt-1">
          <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-glow">
            <Bot className="h-4 w-4 text-white" />
          </div>
        </div>
      )}

      <div
        className={clsx(
          'max-w-[85%] md:max-w-[75%]',
          isUser ? 'order-first' : ''
        )}
      >
        <div
          className={clsx(
            'rounded-2xl px-5 py-3',
            isUser
              ? 'bg-primary-glow border border-primary-light text-text-primary'
              : 'glass text-text-primary'
          )}
        >
          {isUser ? (
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
            </p>
          ) : (
            <div className="markdown-content text-sm">
              <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
            </div>
          )}
        </div>

        {!isUser && (message.confidence != null || message.cacheHit || (message.citations && message.citations.length > 0)) && (
          <div className="mt-3 space-y-3 animate-[slide-up_0.35s_ease-out]">
            {(message.confidence != null || message.cacheHit) && (
              <div className="flex items-center gap-2 flex-wrap">
                {message.confidence != null && (
                  <ConfidenceBadge
                    percentage={message.confidence}
                    note={message.confidenceNote}
                  />
                )}
                {message.cacheHit && <CacheBadge />}
              </div>
            )}

            {message.citations && message.citations.length > 0 && (
              <div>
                <p className="text-[11px] font-semibold text-text-muted tracking-widest uppercase mb-2 flex items-center gap-1.5">
                  📚 Sources
                </p>
                <div className="space-y-2">
                  {message.citations.map((citation) => (
                    <SourceCard key={citation.index} citation={citation} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="shrink-0 mt-1">
          <div className="h-8 w-8 rounded-xl bg-surface-700 border border-glass-border flex items-center justify-center">
            <User className="h-4 w-4 text-text-secondary" />
          </div>
        </div>
      )}
    </div>
  );
}
