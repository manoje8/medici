import { useEffect, useRef } from 'react';

import { MessageBubble } from '@/features/chat/MessageBubble';
import { WelcomeMessage } from '@/features/chat/WelcomeMessage';
import { useAppSelector } from '@/store/hooks';

export function MessageList() {
  const messages = useAppSelector((s) => s.chat.messages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return <WelcomeMessage />;
  }

  return (
    <div className="px-4 py-6 space-y-1">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
