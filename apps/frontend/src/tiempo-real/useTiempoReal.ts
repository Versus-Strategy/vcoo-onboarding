import { useEffect } from 'react';
import RealtimeManager from './RealtimeManager';

let realtimeManager: RealtimeManager | null = null;

export const useTiempoReal = () => {
  useEffect(() => {
    // Initialize real-time manager on mount
    if (!realtimeManager) {
      realtimeManager = new RealtimeManager();
      realtimeManager.connect();
    }

    // Cleanup on unmount
    return () => {
      if (realtimeManager) {
        realtimeManager.disconnect();
        realtimeManager = null;
      }
    };
  }, []);

  return realtimeManager;
};
