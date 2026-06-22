import { useEffect, useState, useRef } from 'react';
import { getVCOOLogs } from '../api/client';

export interface CommandLog {
  id: string;
  cmd_id: string;
  chunk: string;
  stream: string;
  created_at: string;
}

interface LogChunk {
  chunk: string;
  stream: string;
}

/**
 * Polls /vcoo/{id}/logs every 3s and returns flat log lines.
 * Much more reliable than Supabase Realtime subscriptions.
 */
export function useRealtimeLogs(vcooId: string | null) {
  const [logs, setLogs] = useState<CommandLog[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const interval = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!vcooId) {
      setLogs([]);
      return;
    }

    seenIds.current = new Set();
    setLogs([]);

    const fetchLogs = async () => {
      try {
        const data = await getVCOOLogs(vcooId);
        const newLogs: CommandLog[] = [];
        for (const cmd of data.commands || []) {
          for (const log of (cmd.logs || []) as LogChunk[]) {
            const id = `${cmd.cmd_id}:${log.chunk.substring(0, 40)}`;
            if (!seenIds.current.has(id)) {
              seenIds.current.add(id);
              newLogs.push({
                id,
                cmd_id: cmd.cmd_id,
                chunk: log.chunk,
                stream: log.stream,
                created_at: new Date().toISOString(),
              });
            }
          }
        }
        if (newLogs.length > 0) {
          setLogs(prev => [...prev, ...newLogs].slice(-200)); // keep last 200 entries
        }
      } catch {
        // silent — will retry next tick
      }
    };

    fetchLogs();
    interval.current = setInterval(fetchLogs, 3000);

    return () => {
      if (interval.current) clearInterval(interval.current);
    };
  }, [vcooId]);

  return logs;
}
