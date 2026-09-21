import { Bot } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { PipelineProgress } from '@/features/chat/PipelineProgress';
import { useAppSelector } from '@/store/hooks';

/**
 * Renders the currently streaming assistant response:
 *   1. Pipeline progress stages (animated)
 *   2. Token-by-token answer with blinking cursor
 */
export function StreamingAnswer() {
  const streamingTokens = useAppSelector((s) => s.chat.streamingTokens);
  const pipelineStages = useAppSelector((s) => s.chat.pipelineStages);

  return (
    <div className="px-4 py-4 animate-[fade-in_0.3s_ease-out]">
      <div className="flex gap-3">
        <div className="shrink-0 mt-1">
          <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-glow animate-[pulse-soft_2s_ease-in-out_infinite]">
            <Bot className="h-4 w-4 text-white" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          {pipelineStages.length > 0 && (
            <PipelineProgress stages={pipelineStages} />
          )}

          {streamingTokens && (
            <div className="glass rounded-2xl px-5 py-3 mt-2">
              <div className="markdown-content text-sm">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {streamingTokens}
                </Markdown>
                <span className="animate-blink text-primary-light font-bold">▌</span>
              </div>
            </div>
          )}

          {!streamingTokens && pipelineStages.length === 0 && (
            <div className="glass rounded-2xl px-5 py-3">
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-primary/60 animate-[pulse-soft_1s_ease-in-out_infinite]" />
                <span className="h-2 w-2 rounded-full bg-primary/60 animate-[pulse-soft_1s_ease-in-out_0.2s_infinite]" />
                <span className="h-2 w-2 rounded-full bg-primary/60 animate-[pulse-soft_1s_ease-in-out_0.4s_infinite]" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
