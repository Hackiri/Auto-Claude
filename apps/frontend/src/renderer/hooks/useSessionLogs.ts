import { useMemo, useCallback } from 'react';
import { useAgentSessionsStore } from '../stores/agent-sessions-store';
import type { TaskLogEntry } from '../../shared/types';

/**
 * Hook to get logs for a specific session
 */
export function useSessionLogs(sessionId: string | null) {
  // Subscribe to the entire sessionLogs Map to detect changes
  const sessionLogs = useAgentSessionsStore((state) => state.sessionLogs);
  const appendLogs = useAgentSessionsStore((state) => state.appendLogs);
  const clearSessionLogs = useAgentSessionsStore((state) => state.clearSessionLogs);
  const sessions = useAgentSessionsStore((state) => state.sessions);

  // Find the session to get both id and specId for log lookup
  const session = useMemo(() => {
    if (!sessionId) return null;
    return sessions.find((s) => s.id === sessionId || s.specId === sessionId) || null;
  }, [sessions, sessionId]);

  // Get logs for this specific session - check both id and specId
  // Logs might be stored under either key depending on how IPC events reference the task
  const logs = useMemo(() => {
    if (!sessionId) return [];
    // Try sessionId first, then try specId if session exists
    let foundLogs = sessionLogs.get(sessionId);
    if (!foundLogs && session?.specId && session.specId !== sessionId) {
      foundLogs = sessionLogs.get(session.specId);
    }
    if (!foundLogs && session?.id && session.id !== sessionId) {
      foundLogs = sessionLogs.get(session.id);
    }
    return foundLogs || [];
  }, [sessionId, sessionLogs, session]);

  const isStreaming = session?.logStreamActive ?? false;

  const addLogs = useCallback(
    (newLogs: TaskLogEntry[]) => {
      if (sessionId) {
        appendLogs(sessionId, newLogs);
      }
    },
    [sessionId, appendLogs]
  );

  const clearLogs = useCallback(() => {
    if (sessionId) {
      clearSessionLogs(sessionId);
    }
  }, [sessionId, clearSessionLogs]);

  // Group logs by phase for display
  const logsByPhase = useMemo(() => {
    const grouped: Record<string, TaskLogEntry[]> = {
      planning: [],
      coding: [],
      validation: []
    };

    for (const log of logs) {
      const phase = log.phase || 'coding';
      if (!grouped[phase]) {
        grouped[phase] = [];
      }
      grouped[phase].push(log);
    }

    return grouped;
  }, [logs]);

  return {
    logs,
    logsByPhase,
    isStreaming,
    addLogs,
    clearLogs,
    logCount: logs.length
  };
}

/**
 * Hook to get the latest log entry for a session (useful for status display)
 */
export function useLatestSessionLog(sessionId: string | null): TaskLogEntry | null {
  const sessionLogs = useAgentSessionsStore((state) => state.sessionLogs);

  return useMemo(() => {
    if (!sessionId) return null;
    const logs = sessionLogs.get(sessionId) || [];
    return logs.length > 0 ? logs[logs.length - 1] : null;
  }, [sessionId, sessionLogs]);
}
