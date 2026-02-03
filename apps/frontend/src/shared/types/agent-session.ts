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

// --- Session History & Persistence Types ---

/**
 * Phase duration record - tracks time spent in each execution phase
 */
export interface PhaseDuration {
  phase: ExecutionPhase;
  durationMs: number;
  startedAt: string;      // ISO string for serialization
  completedAt: string;    // ISO string for serialization
}

/**
 * Log summary - compact summary of session logs for history storage
 */
export interface LogSummary {
  totalEntries: number;
  errorCount: number;
  warningCount: number;
  phaseTransitions: number;
}

/**
 * Session History Entry - serializable version of AgentSession for disk persistence
 * Stored as individual JSON files in session history directory
 */
export interface SessionHistoryEntry {
  id: string;
  specId: string;
  projectId: string;
  title: string;
  status: SessionStatus;
  success: boolean;
  createdAt: string;      // ISO string
  startedAt?: string;     // ISO string
  completedAt?: string;   // ISO string
  durationMs: number;     // Total execution time
  phaseDurations: PhaseDuration[];
  overallProgress: number;
  subtaskTotal: number;
  subtaskCompleted: number;
  logSummary: LogSummary;
  updatedAt: string;      // ISO string - used for sorting
}

// --- Session Metrics & Analytics Types ---

/**
 * Aggregated session metrics computed from history
 */
export interface SessionMetrics {
  totalSessions: number;
  successCount: number;
  failureCount: number;
  successRate: number;           // 0-1
  averageDurationMs: number;
  medianDurationMs: number;
  averagePhaseDurations: Record<string, number>;  // phase name → avg ms
}

/**
 * Data point for execution time chart
 */
export interface ExecutionTimeDataPoint {
  sessionId: string;
  title: string;
  durationMs: number;
  completedAt: string;   // ISO string
  success: boolean;
}

/**
 * Data point for success rate chart
 */
export interface SuccessRateDataPoint {
  name: string;
  value: number;
  color: string;
}

/**
 * Data point for phase duration chart
 */
export interface PhaseDurationDataPoint {
  sessionTitle: string;
  [phase: string]: string | number;  // dynamic phase keys with ms values
}

/**
 * Data point for trend chart
 */
export interface TrendDataPoint {
  date: string;           // ISO date string (day granularity)
  averageDurationMs: number;
  successRate: number;    // 0-1
  sessionCount: number;
}

// --- Log Filter Types ---

/**
 * Log entry type for filtering
 */
export type LogEntryType = 'error' | 'info' | 'phase' | 'tool' | 'warning';

/**
 * Log filter options for the log filter bar
 */
export interface LogFilterOptions {
  types: LogEntryType[];           // Filter by log entry types (empty = all)
  phase: string | null;            // Filter by specific phase (null = all)
  searchText: string;              // Text search within log messages
  dateRange?: {
    from: string;                  // ISO string
    to: string;                    // ISO string
  };
}

/**
 * Detected error pattern in logs
 */
export interface ErrorPattern {
  pattern: string;
  count: number;
  firstOccurrence: number;        // Log entry index
  lastOccurrence: number;         // Log entry index
}

/**
 * Default log filter options
 */
export const DEFAULT_LOG_FILTER: LogFilterOptions = {
  types: [],
  phase: null,
  searchText: '',
};
