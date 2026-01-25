/**
 * Agent Session types
 *
 * An "Agent Session" represents a spec build execution. It's 1:1 with a spec/task.
 * This enhances the existing task model with real-time monitoring capabilities.
 */

import type { ExecutionPhase, ImplementationPlan, SubtaskStatus, TaskLogEntry } from './task';

/**
 * Session status - maps to task lifecycle
 */
export type SessionStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'archived';

/**
 * Agent Session - represents a spec build execution
 * Provides real-time monitoring of active agent builds
 */
export interface AgentSession {
  id: string;                    // Same as taskId/specId
  specId: string;
  projectId: string;
  title: string;                 // From spec feature name
  status: SessionStatus;
  currentPhase: ExecutionPhase;
  phaseProgress: number;         // 0-100 within current phase
  overallProgress: number;       // 0-100 overall
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  archivedAt?: Date;
  plan?: ImplementationPlan;
  logStreamActive: boolean;
}

/**
 * Session Task - represents a subtask within a session
 * Used for Kanban-style visualization
 */
export interface SessionTask {
  id: string;
  phaseId: string;
  phaseName: string;
  description: string;
  status: SubtaskStatus;
  files_to_create: string[];
  files_to_modify: string[];
  verification?: {
    type: 'command' | 'browser';
    run?: string;
    scenario?: string;
  };
  updatedAt?: Date;
}

/**
 * Session log state - tracks logs per session
 */
export interface SessionLogState {
  sessionId: string;
  logs: TaskLogEntry[];
  isStreaming: boolean;
}

/**
 * Maps TaskStatus to SessionStatus
 */
export function taskStatusToSessionStatus(
  taskStatus: string,
  isRunning: boolean = false
): SessionStatus {
  switch (taskStatus) {
    case 'backlog':
      return 'pending';
    case 'in_progress':
      return isRunning ? 'running' : 'paused';
    case 'ai_review':
    case 'human_review':
      return 'paused';
    case 'pr_created':
    case 'done':
      return 'completed';
    case 'error':
      return 'failed';
    default:
      return 'pending';
  }
}

/**
 * Checks if a session is active (running or paused but in progress)
 */
export function isActiveSession(session: AgentSession): boolean {
  return session.status === 'running' || session.status === 'paused' || session.status === 'pending';
}

/**
 * Checks if a session is archived
 */
export function isArchivedSession(session: AgentSession): boolean {
  return session.status === 'archived';
}
