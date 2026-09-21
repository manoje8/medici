import type { PipelineStage } from '@/types';

interface PipelineProgressProps {
  stages: PipelineStage[];
}

export function PipelineProgress({ stages }: PipelineProgressProps) {
  return (
    <div className="space-y-1 mb-2">
      {stages.map((stage, i) => (
        <div
          key={stage.id}
          className="flex items-center gap-2 text-xs text-text-muted animate-[fade-in_0.3s_ease-out]"
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <span className="text-sm">{stage.icon}</span>
          <span>{stage.message}…</span>
        </div>
      ))}
    </div>
  );
}
