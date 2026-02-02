/**
 * Session History IPC handlers
 * Handles listing, loading, deleting historical agent sessions and computing metrics
 */

import { ipcMain } from 'electron';
import path from 'path';
import { readdir, readFile, unlink, stat } from 'fs/promises';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';
import type { SessionHistoryEntry, SessionMetrics } from '../../shared/types/agent-session';
import { projectStore } from '../project-store';

// Debug logging helper
const DEBUG = process.env.DEBUG === 'true' || process.env.NODE_ENV === 'development';

function debugLog(message: string, data?: unknown): void {
  if (DEBUG) {
    if (data !== undefined) {
      console.debug(`[Session History] ${message}`, data);
    } else {
      console.debug(`[Session History] ${message}`);
    }
  }
}

/**
 * Get the session history directory for a project
 */
function getSessionHistoryDir(projectPath: string): string {
  return path.join(projectPath, '.auto-claude', 'session-history');
}

/**
 * Load a session history entry from a JSON file
 */
async function loadSessionFromFile(filePath: string): Promise<SessionHistoryEntry | null> {
  try {
    const content = await readFile(filePath, 'utf-8');
    return JSON.parse(content) as SessionHistoryEntry;
  } catch (error) {
    debugLog(`Failed to load session file: ${filePath}`, error);
    return null;
  }
}

/**
 * Compute aggregated metrics from session history entries
 */
function computeMetrics(sessions: SessionHistoryEntry[]): SessionMetrics {
  const totalSessions = sessions.length;
  const successCount = sessions.filter(s => s.success).length;
  const failureCount = totalSessions - successCount;
  const successRate = totalSessions > 0 ? successCount / totalSessions : 0;

  const durations = sessions
    .filter(s => s.durationMs > 0)
    .map(s => s.durationMs)
    .sort((a, b) => a - b);

  const averageDurationMs = durations.length > 0
    ? durations.reduce((sum, d) => sum + d, 0) / durations.length
    : 0;

  const medianDurationMs = durations.length > 0
    ? durations.length % 2 === 0
      ? (durations[durations.length / 2 - 1] + durations[durations.length / 2]) / 2
      : durations[Math.floor(durations.length / 2)]
    : 0;

  // Compute average phase durations
  const phaseAccum: Record<string, { total: number; count: number }> = {};
  for (const session of sessions) {
    for (const pd of session.phaseDurations) {
      if (!phaseAccum[pd.phase]) {
        phaseAccum[pd.phase] = { total: 0, count: 0 };
      }
      phaseAccum[pd.phase].total += pd.durationMs;
      phaseAccum[pd.phase].count += 1;
    }
  }

  const averagePhaseDurations: Record<string, number> = {};
  for (const [phase, accum] of Object.entries(phaseAccum)) {
    averagePhaseDurations[phase] = accum.count > 0 ? accum.total / accum.count : 0;
  }

  return {
    totalSessions,
    successCount,
    failureCount,
    successRate,
    averageDurationMs,
    medianDurationMs,
    averagePhaseDurations,
  };
}

/**
 * Register all session history IPC handlers
 */
export function registerSessionHistoryHandlers(): void {
  // List all historical sessions for a project
  ipcMain.handle(
    IPC_CHANNELS.SESSION_HISTORY_LIST,
    async (_event, projectId: string): Promise<IPCResult<SessionHistoryEntry[]>> => {
      debugLog('listSessionHistory called', { projectId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const historyDir = getSessionHistoryDir(project.path);

        let files: string[];
        try {
          files = await readdir(historyDir);
        } catch {
          // Directory doesn't exist yet - no history
          return { success: true, data: [] };
        }

        const jsonFiles = files.filter(f => f.endsWith('.json'));
        const sessions: SessionHistoryEntry[] = [];

        for (const file of jsonFiles) {
          const session = await loadSessionFromFile(path.join(historyDir, file));
          if (session) {
            sessions.push(session);
          }
        }

        // Sort by updatedAt descending (most recent first)
        sessions.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

        debugLog(`Loaded ${sessions.length} session history entries`);
        return { success: true, data: sessions };
      } catch (error) {
        debugLog('Failed to list session history', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to list session history',
        };
      }
    }
  );

  // Load a single session by ID
  ipcMain.handle(
    IPC_CHANNELS.SESSION_HISTORY_LOAD,
    async (_event, projectId: string, sessionId: string): Promise<IPCResult<SessionHistoryEntry>> => {
      debugLog('loadSessionHistory called', { projectId, sessionId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const filePath = path.join(getSessionHistoryDir(project.path), `${sessionId}.json`);
        const session = await loadSessionFromFile(filePath);

        if (!session) {
          return { success: false, error: 'Session not found' };
        }

        return { success: true, data: session };
      } catch (error) {
        debugLog('Failed to load session', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to load session',
        };
      }
    }
  );

  // Delete a session from history
  ipcMain.handle(
    IPC_CHANNELS.SESSION_HISTORY_DELETE,
    async (_event, projectId: string, sessionId: string): Promise<IPCResult> => {
      debugLog('deleteSessionHistory called', { projectId, sessionId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const filePath = path.join(getSessionHistoryDir(project.path), `${sessionId}.json`);

        // Check file exists before deleting
        await stat(filePath);
        await unlink(filePath);

        debugLog(`Deleted session history: ${sessionId}`);
        return { success: true };
      } catch (error) {
        debugLog('Failed to delete session', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to delete session',
        };
      }
    }
  );

  // Get aggregated metrics for analytics
  ipcMain.handle(
    IPC_CHANNELS.SESSION_HISTORY_METRICS,
    async (_event, projectId: string): Promise<IPCResult<SessionMetrics>> => {
      debugLog('getSessionMetrics called', { projectId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const historyDir = getSessionHistoryDir(project.path);

        let files: string[];
        try {
          files = await readdir(historyDir);
        } catch {
          // No history directory - return empty metrics
          return {
            success: true,
            data: computeMetrics([]),
          };
        }

        const jsonFiles = files.filter(f => f.endsWith('.json'));
        const sessions: SessionHistoryEntry[] = [];

        for (const file of jsonFiles) {
          const session = await loadSessionFromFile(path.join(historyDir, file));
          if (session) {
            sessions.push(session);
          }
        }

        const metrics = computeMetrics(sessions);
        debugLog('Computed metrics', metrics);

        return { success: true, data: metrics };
      } catch (error) {
        debugLog('Failed to compute metrics', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to compute metrics',
        };
      }
    }
  );
}
