import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export interface CommandLog {
  id: string;
  cmd_id: string;
  chunk: string;
  stream: string;
  created_at: string;
}

export function useRealtimeLogs(vcooId: string | null) {
  const [logs, setLogs] = useState<CommandLog[]>([]);

  useEffect(() => {
    if (!vcooId) return;

    setLogs([]);

    // Load existing logs via REST
    supabase
      .from('command_logs')
      .select('*')
      .order('created_at', { ascending: true })
      .then(({ data, error }) => {
        if (data) setLogs(data);
        if (error) console.error('Failed to load logs:', error);
      });

    // Subscribe to new inserts
    const channel = supabase
      .channel(`logs-${vcooId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'command_logs',
        },
        (payload) => {
          setLogs((prev) => [...prev, payload.new as CommandLog]);
        },
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') console.log(`Realtime connected for ${vcooId}`);
        if (status === 'CHANNEL_ERROR') console.error('Realtime error');
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [vcooId]);

  return logs;
}
