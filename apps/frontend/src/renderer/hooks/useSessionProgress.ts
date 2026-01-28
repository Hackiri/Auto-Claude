import { useMemo } from 'react';
import { useAgentSessionsStore } from '../stores/agent-sessions-store';
import type { AgentSession, SessionTask, SubtaskStatus } from '../../shared/types';

/**
 * Extract SessionTasks from session's implementation plan
 * This is done in the hook to ensure reactivity when plan updates
 *
 * If session is running but no tasks are marked in_progress, we infer
 * the first pending task as in_progress for better UX feedback.
 */
function extractTasksFromSession(session: AgentSession | null): SessionTask[] {
  if (!session?.plan?.phases || !Array.isArray(session.plan.phases)) {
    return [];
  }

  const tasks: SessionTask[] = [];

  for (const phase of session.plan.phases) {
    if (!phase.subtasks || !Array.isArray(phase.subtasks)) continue;

    for (const subtask of phase.subtasks) {
      tasks.push({
        id: subtask.id || `${phase.phase}-${tasks.length}`,
        phaseId: String(phase.phase),
        phaseName: phase.name || `Phase ${phase.phase}`,
        description: subtask.description || 'No description',
        status: (subtask.status as SubtaskStatus) || 'pending',
        files_to_create: [],
        files_to_modify: [],
        verification: subtask.verification as SessionTask['verification'],
        updatedAt: new Date()
      });
    }
  }

  // If session is running (in coding phase) but no tasks are marked in_progress,
  // infer the first pending task as in_progress for visual feedback
  const isSessionActive = session.status === 'running' &&
    session.currentPhase === 'coding';
  const hasInProgressTask = tasks.some((t) => t.status === 'in_progress');

  if (isSessionActive && !hasInProgressTask) {
    const firstPendingIndex = tasks.findIndex((t) => t.status === 'pending');
    if (firstPendingIndex !== -1) {
      tasks[firstPendingIndex] = {
        ...tasks[firstPendingIndex],
        status: 'in_progress'
      };
    }
  }

  return tasks;
}

/**
 * Hook to get progress information for a specific session
 */
export function useSessionProgress(sessionId: string | null) {
  // Subscribe to sessions array to detect plan updates
  const sessions = useAgentSessionsStore((state) => state.sessions);

  const session = useMemo(() => {
    if (!sessionId) return null;
    return sessions.find((s) => s.id === sessionId || s.specId === sessionId) || null;
  }, [sessions, sessionId]);

  // Extract tasks from session's plan - recomputes when session changes
  const tasks = useMemo(() => {
    return extractTasksFromSession(session);
  }, [session]);

  const taskStats = useMemo(() => {
    const pending = tasks.filter((t) => t.status === 'pending').length;
    const inProgress = tasks.filter((t) => t.status === 'in_progress').length;
    const completed = tasks.filter((t) => t.status === 'completed').length;
    const failed = tasks.filter((t) => t.status === 'failed').length;
    const total = tasks.length;

    return {
      pending,
      inProgress,
      completed,
      failed,
      total,
      completedPercentage: total > 0 ? Math.round((completed / total) * 100) : 0
    };
  }, [tasks]);

  return {
    session,
    tasks,
    taskStats,
    isRunning: session?.status === 'running',
    isPaused: session?.status === 'paused',
    isCompleted: session?.status === 'completed',
    isFailed: session?.status === 'failed'
  };
}

/**
 * Hook to get all active sessions with their progress
 */
export function useActiveSessions(): AgentSession[] {
  const sessions = useAgentSessionsStore((state) => state.sessions);
  return useMemo(() => {
    return sessions.filter((s) =>
      s.status === 'running' || s.status === 'paused' || s.status === 'pending'
    );
  }, [sessions]);
}

/**
 * Hook to get all archived sessions
 */
export function useArchivedSessions(): AgentSession[] {
  const sessions = useAgentSessionsStore((state) => state.sessions);
  return useMemo(() => {
    return sessions.filter((s) => s.status === 'archived');
  }, [sessions]);
}

/**
 * Hook to get session tasks grouped by status for Kanban view
 */
export function useSessionTasksByStatus(sessionId: string | null): {
  pending: SessionTask[];
  inProgress: SessionTask[];
  completed: SessionTask[];
} {
  const sessions = useAgentSessionsStore((state) => state.sessions);

  return useMemo(() => {
    if (!sessionId) {
      return { pending: [], inProgress: [], completed: [] };
    }

    const session = sessions.find((s) => s.id === sessionId || s.specId === sessionId);
    const tasks = extractTasksFromSession(session || null);

    return {
      pending: tasks.filter((t) => t.status === 'pending'),
      inProgress: tasks.filter((t) => t.status === 'in_progress'),
      completed: tasks.filter((t) => t.status === 'completed' || t.status === 'failed')
    };
  }, [sessionId, sessions]);
}
