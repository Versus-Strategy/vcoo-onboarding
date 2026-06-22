import { useEffect, useState, useRef } from 'react';
import { getVCOOLogs } from '../api/client';

export interface CommandLog {
  id: string;
  cmd_id: string;
  chunk: string;
  stream: string;
  created_at: string;
}

/**
 * Polls /vcoo/{id}/logs every 3s and returns flat log lines.
 * Shows both command entries (what ran) and real log chunks.
 */
export function useRealtimeLogs(vcooId: string | null) {
  const [logs, setLogs] = useState<CommandLog[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

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
          // Add command entry as a system log
          const cmdId = `cmd:${cmd.cmd_id}`;
          if (!seenIds.current.has(cmdId)) {
            seenIds.current.add(cmdId);
            const statusIcon = cmd.status === 'done' ? '✓' : cmd.status === 'error' ? '✗' : '…';
            newLogs.push({
              id: cmdId,
              cmd_id: cmd.cmd_id,
              chunk: `[${statusIcon}] ${cmd.command} (${cmd.step})${cmd.result ? ' → ' + cmd.result.slice(0, 200) : ''}`,
              stream: cmd.status === 'error' ? 'stderr' : 'system',
              created_at: new Date().toISOString(),
            });
          }
          // Add real log chunks
          for (const log of cmd.logs || []) {
            const id = `${cmd.cmd_id}:${log.chunk?.substring(0, 40) || Math.random()}`;
            if (!seenIds.current.has(id)) {
              seenIds.current.add(id);
              newLogs.push({
                id,
                cmd_id: cmd.cmd_id,
                chunk: log.chunk || '',
                stream: log.stream || 'stdout',
                created_at: new Date().toISOString(),
              });
            }
          }
        }
        if (newLogs.length > 0) {
          setLogs(prev => [...prev, ...newLogs].slice(-300));
        }
      } catch {
        // silent retry
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [vcooId]);

  return logs;
}
