import { Send, Square } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { addMessage } from '@/features/chat/chatSlice';
import { useSSEStream } from '@/hooks/useSSEStream';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { Icon } from "@iconify/react";
import { UploadPanel } from '../upload/UploadPanel';

export function ChatInput() {
  const dispatch = useAppDispatch();
  const isProcessing = useAppSelector((s) => s.chat.isProcessing);
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { startStream, cancelStream } = useSSEStream();


  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isProcessing) return;

    // Add user message
    dispatch(
      addMessage({
        id: uuidv4(),
        role: 'user',
        content: trimmed,
        timestamp: Date.now(),
      })
    );

    setInput('');

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    startStream(trimmed);
  }, [input, isProcessing, dispatch, startStream]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  };

  const handleVoiceInput = () => {
    // Placeholder for voice input functionality
    console.log('Voice input triggered');
  }

  return (
    <div className="py-3 px-4">
      <div className="flex items-end gap-3 glass rounded-2xl px-4 py-3 shadow-card">
        <UploadPanel />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleTextareaChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything"
          disabled={isProcessing}
          rows={1}
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted resize-none focus:outline-none min-h-[24px] max-h-[160px] leading-relaxed disabled:opacity-50"
        />

        {isProcessing ? (
          <button
            onClick={cancelStream}
            className="shrink-0 h-9 w-9 rounded-xl bg-error-bg hover:bg-error-bg border border-error-border flex items-center justify-center text-error transition-all cursor-pointer"
            title="Stop generating"
          >
            <Square className="h-4 w-4" />
          </button>
        ) : input.trim() ? (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="shrink-0 h-9 w-9 rounded-xl bg-gradient-to-br from-primary to-primary-dark hover:from-primary-light hover:to-primary flex items-center justify-center text-white shadow-md transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            title="Send message"
          >
            <Icon icon="griddy-icons:send-alt-02-filled" className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={handleVoiceInput}
            className="shrink-0 h-9 w-9 rounded-xl bg-gradient-to-br from-primary-light to-primary-dark hover:from-primary-light hover:to-primary flex items-center justify-center text-white transition-all cursor-pointer"
            title="Voice input"
          >
            <Icon icon="wpf:audio-wave" className="h-4 w-4" />
          </button>
        )}
      </div>

      <p className="text-[10px] text-text-muted text-center mt-2">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
