import { clsx } from 'clsx';
import { AlertTriangle, CheckCircle, Info, X, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';

export interface ToastData {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

interface ToastProps {
  toast: ToastData;
  onDismiss: (id: string) => void;
}

const icons = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorClasses = {
  success: 'border-success/40 text-success',
  error: 'border-error/40 text-error',
  warning: 'border-warning/40 text-warning',
  info: 'border-primary/40 text-primary-light',
};

export function Toast({ toast, onDismiss }: ToastProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setIsVisible(true));
    const timer = setTimeout(
      () => {
        setIsVisible(false);
        setTimeout(() => onDismiss(toast.id), 300);
      },
      toast.duration ?? 4000
    );
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  const Icon = icons[toast.type];

  return (
    <div
      className={clsx(
        'glass rounded-xl border px-4 py-3 flex items-center gap-3 min-w-[300px] max-w-[420px] shadow-card transition-all duration-300',
        colorClasses[toast.type],
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      )}
      role="alert"
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="text-sm text-text-primary flex-1">{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-text-muted hover:text-text-primary transition-colors cursor-pointer"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
