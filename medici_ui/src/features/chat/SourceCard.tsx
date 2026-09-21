import type { Citation } from '@/types';

interface SourceCardProps {
  citation: Citation;
}

export function SourceCard({ citation }: SourceCardProps) {
  return (
    <div className="glass rounded-xl px-4 py-3 hover:border-primary/30 hover:shadow-glow transition-all duration-200 group">
      <div className="flex items-center gap-2">
        <span className="shrink-0 h-5 w-5 rounded-full bg-primary/20 text-primary-light text-[10px] font-bold flex items-center justify-center">
          {citation.index}
        </span>

        <span className="text-xs font-semibold text-text-primary truncate">
          {citation.filename}
        </span>

        <span className="text-[10px] font-medium text-primary-light/70 bg-primary/10 px-2 py-0.5 rounded-md shrink-0">
          § {citation.section}
        </span>
      </div>

      <p className="text-[11px] text-text-muted mt-1.5 truncate group-hover:text-text-secondary transition-colors">
        {citation.path}
      </p>
    </div>
  );
}
