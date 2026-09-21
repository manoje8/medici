import { AlertTriangle } from 'lucide-react';

interface HealthBannerProps {
  isHealthy: boolean | null;
}

export function HealthBanner({ isHealthy }: HealthBannerProps) {
  if (isHealthy === null || isHealthy) return null;

  return (
    <div className="animate-[fade-in_0.3s_ease-out] bg-warning-bg border border-warning-border rounded-xl px-4 py-3 flex items-center gap-3 mx-4 mt-4">
      <AlertTriangle className="h-5 w-5 text-warning shrink-0" />
      <p className="text-sm text-warning font-medium">
        Backend service is not accessible. Some features may be limited.
      </p>
    </div>
  );
}
