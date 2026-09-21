import { useEffect, useState } from 'react';

import type { HealthStatus } from '@/types';
import { API_BASE_URL, HEALTH_CHECK_INTERVAL_MS } from '@/utils/constants';

/**
 * Polls `GET /health` at a configurable interval.
 * Returns the current health status and whether the backend is reachable.
 */
export function useHealthCheck() {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [healthData, setHealthData] = useState<HealthStatus | null>(null);

  useEffect(() => {
    let mounted = true;

    const check = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (!mounted) return;

        if (res.ok || res.status === 503) {
          const data: HealthStatus = await res.json();
          setHealthData(data);
          setIsHealthy(data.status === 'ok');
        } else {
          setIsHealthy(false);
          setHealthData(null);
        }
      } catch {
        if (!mounted) return;
        setIsHealthy(false);
        setHealthData(null);
      }
    };

    check();
    const interval = setInterval(check, HEALTH_CHECK_INTERVAL_MS);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { isHealthy, healthData };
}
