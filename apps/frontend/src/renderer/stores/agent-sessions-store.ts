import { create } from 'zustand';
import type {
  AgentSession,
  SessionTask,
  SessionStatus,
  ImplementationPlan,
  ExecutionPhase,
  TaskLogEntry,
  Task
} from '../../shared/types';
import { taskStatusToSessionStatus, isActiveSession, isArchivedSession } from '../../shared/types/agent-session';
import { debugLog } from '../../shared/utils/debug-logger';

interface AgentSessionsState {
  sessions: AgentSession[];
  selectedSessionId: string | null;
  activeTab: 'active' | 'archived';
  sessionLogs: Map<string, TaskLogEntry[]>;
  isLoading: boolean;

  // Actions
  setSessions: (sessions: AgentSession[]) => void;
  addSession: (session: AgentSession) => void;
  updateSession: (sessionId: string, updates: Partial<AgentSession>) => void;
  updateSessionFromPlan: (sessionId: string, plan: ImplementationPlan) => void;
  updateSessionPhase: (sessionId: string, phase: ExecutionPhase, progress: number) => void;
  updateSessionStatus: (sessionId: string, status: SessionStatus) => void;
  archiveSession: (sessionId: string) => void;
  selectSession: (sessionId: string | null) => void;
  setActiveTab: (tab: 'active' | 'archived') => void;
  appendLogs: (sessionId: string, logs: TaskLogEntry[]) => void;
  clearSessionLogs: (sessionId: string) => void;
  setLoading: (loading: boolean) => void;
  clearSessions: () => void;

  // Sync from tasks
  syncFromTasks: (tasks: Task[]) => void;

  // Selectors
  getActiveSessions: () => AgentSession[];
  getArchivedSessions: () => AgentSession[];
  getSessionTasks: (sessionId: string) => SessionTask[];
  getSelectedSession: () => AgentSession | undefined;
  getSessionLogs: (sessionId: string) => TaskLogEntry[];
}

/**
 * Helper to find session index by id or specId.
 * Returns -1 if not found.
 */
function findSessionIndex(sessions: AgentSession[], sessionId: string): number {
  return sessions.findIndex((s) => s.id === sessionId || s.specId === sessionId);
}

/**
 * Helper to update a single session efficiently.
 */
function updateSessionAtIndex(
  sessions: AgentSession[],
  index: number,
  updater: (session: AgentSession) => AgentSession
): AgentSession[] {
  if (index < 0 || index >= sessions.length) return sessions;

  const updatedSession = updater(sessions[index]);

  if (updatedSession === sessions[index]) {
    return sessions;
  }

  const newSessions = [...sessions];
  newSessions[index] = updatedSession;

  return newSessions;
}

/**
 * Convert a Task to an AgentSession
 */
function taskToSession(task: Task): AgentSession {
  const isRunning = Boolean(
    task.status === 'in_progress' &&
    task.executionProgress?.phase &&
    !['idle', 'complete', 'failed'].includes(task.executionProgress.phase)
  );

  return {
    id: task.id,
    specId: task.specId,
    projectId: task.projectId,
    title: task.title,
    status: taskStatusToSessionStatus(task.status, isRunning),
    currentPhase: task.executionProgress?.phase || 'idle',
    phaseProgress: task.executionProgress?.phaseProgress || 0,
    overallProgress: task.executionProgress?.overallProgress || 0,
    createdAt: task.createdAt,
    startedAt: task.executionProgress?.startedAt ? new Date(task.executionProgress.startedAt) : undefined,
    completedAt: task.status === 'done' || task.status === 'pr_created' ? task.updatedAt : undefined,
    archivedAt: task.metadata?.archivedAt ? new Date(task.metadata.archivedAt) : undefined,
    logStreamActive: isRunning
  };
}

/**
 * Extract SessionTasks from an ImplementationPlan
 */
function extractSessionTasks(plan: ImplementationPlan): SessionTask[] {
  if (!plan.phases || !Array.isArray(plan.phases)) {
    return [];
  }

  const tasks: SessionTask[] = [];

  for (const phase of plan.phases) {
    if (!phase.subtasks || !Array.isArray(phase.subtasks)) continue;

    for (const subtask of phase.subtasks) {
      tasks.push({
        id: subtask.id || `${phase.phase}-${tasks.length}`,
        phaseId: String(phase.phase),
        phaseName: phase.name || `Phase ${phase.phase}`,
        description: subtask.description || 'No description',
        status: subtask.status || 'pending',
        files_to_create: [],
        files_to_modify: [],
        verification: subtask.verification as SessionTask['verification'],
        updatedAt: new Date()
      });
    }
  }

  return tasks;
}

export const useAgentSessionsStore = create<AgentSessionsState>((set, get) => ({
  sessions: [],
  selectedSessionId: null,
  activeTab: 'active',
  sessionLogs: new Map(),
  isLoading: false,

  setSessions: (sessions) => set({ sessions }),

  addSession: (session) =>
    set((state) => ({
      sessions: [session, ...state.sessions]
    })),

  updateSession: (sessionId, updates) =>
    set((state) => {
      const index = findSessionIndex(state.sessions, sessionId);
      if (index === -1) return state;

      return {
        sessions: updateSessionAtIndex(state.sessions, index, (s) => ({
          ...s,
          ...updates
        }))
      };
    }),

  updateSessionFromPlan: (sessionId, plan) =>
    set((state) => {
      const index = findSessionIndex(state.sessions, sessionId);
      if (index === -1) {
        debugLog('[AgentSessionsStore] Session not found for plan update:', sessionId);
        return state;
      }

      return {
        sessions: updateSessionAtIndex(state.sessions, index, (s) => ({
          ...s,
          plan,
          title: plan.feature || plan.title || s.title
        }))
      };
    }),

  updateSessionPhase: (sessionId, phase, progress) =>
    set((state) => {
      const index = findSessionIndex(state.sessions, sessionId);
      if (index === -1) return state;

      return {
        sessions: updateSessionAtIndex(state.sessions, index, (s) => {
          // Determine if session is now running based on phase
          const isRunning = !['idle', 'complete', 'failed'].includes(phase);
          const newStatus: SessionStatus = phase === 'complete'
            ? 'completed'
            : phase === 'failed'
              ? 'failed'
              : isRunning
                ? 'running'
                : s.status;

          return {
            ...s,
            currentPhase: phase,
            phaseProgress: progress,
            status: newStatus,
            logStreamActive: isRunning
          };
        })
      };
    }),

  updateSessionStatus: (sessionId, status) =>
    set((state) => {
      const index = findSessionIndex(state.sessions, sessionId);
      if (index === -1) return state;

      return {
        sessions: updateSessionAtIndex(state.sessions, index, (s) => ({
          ...s,
          status,
          logStreamActive: status === 'running'
        }))
      };
    }),

  archiveSession: (sessionId) =>
    set((state) => {
      const index = findSessionIndex(state.sessions, sessionId);
      if (index === -1) return state;

      return {
        sessions: updateSessionAtIndex(state.sessions, index, (s) => ({
          ...s,
          status: 'archived' as SessionStatus,
          archivedAt: new Date()
        }))
      };
    }),

  selectSession: (sessionId) => set({ selectedSessionId: sessionId }),

  setActiveTab: (tab) => set({ activeTab: tab }),

  appendLogs: (sessionId, logs) =>
    set((state) => {
      const existingLogs = state.sessionLogs.get(sessionId) || [];
      const newLogs = new Map(state.sessionLogs);
      newLogs.set(sessionId, [...existingLogs, ...logs]);
      return { sessionLogs: newLogs };
    }),

  clearSessionLogs: (sessionId) =>
    set((state) => {
      const newLogs = new Map(state.sessionLogs);
      newLogs.delete(sessionId);
      return { sessionLogs: newLogs };
    }),

  setLoading: (isLoading) => set({ isLoading }),

  clearSessions: () => set({ sessions: [], selectedSessionId: null, sessionLogs: new Map() }),

  syncFromTasks: (tasks) =>
    set((state) => {
      // Convert tasks to sessions, preserving existing session state where possible
      const newSessions: AgentSession[] = tasks.map((task) => {
        const existingSession = state.sessions.find(
          (s) => s.id === task.id || s.specId === task.specId
        );

        if (existingSession) {
          // Update existing session with task data
          const isRunning = Boolean(
            task.status === 'in_progress' &&
            task.executionProgress?.phase &&
            !['idle', 'complete', 'failed'].includes(task.executionProgress.phase)
          );

          return {
            ...existingSession,
            title: task.title,
            status: taskStatusToSessionStatus(task.status, isRunning),
            currentPhase: task.executionProgress?.phase || existingSession.currentPhase,
            phaseProgress: task.executionProgress?.phaseProgress ?? existingSession.phaseProgress,
            overallProgress: task.executionProgress?.overallProgress ?? existingSession.overallProgress,
            logStreamActive: isRunning
          };
        }

        // Create new session from task
        return taskToSession(task);
      });

      return { sessions: newSessions };
    }),

  // Selectors
  getActiveSessions: () => {
    const state = get();
    return state.sessions.filter(isActiveSession);
  },

  getArchivedSessions: () => {
    const state = get();
    return state.sessions.filter(isArchivedSession);
  },

  getSessionTasks: (sessionId) => {
    const state = get();
    const session = state.sessions.find(
      (s) => s.id === sessionId || s.specId === sessionId
    );

    if (!session?.plan) {
      return [];
    }

    return extractSessionTasks(session.plan);
  },

  getSelectedSession: () => {
    const state = get();
    if (!state.selectedSessionId) return undefined;
    return state.sessions.find(
      (s) => s.id === state.selectedSessionId || s.specId === state.selectedSessionId
    );
  },

  getSessionLogs: (sessionId) => {
    const state = get();
    return state.sessionLogs.get(sessionId) || [];
  }
}));

/**
 * Sync sessions from tasks - call this when tasks are loaded or updated
 */
export function syncSessionsFromTasks(tasks: Task[]): void {
  useAgentSessionsStore.getState().syncFromTasks(tasks);
}
