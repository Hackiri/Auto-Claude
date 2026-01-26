/**
 * Merge History handlers
 * Handles operations for viewing merge completion history and rollback capability
 */

import { ipcMain } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';
import { projectStore } from '../project-store';
import { spawn } from 'child_process';
import path from 'path';
import { getConfiguredPythonPath } from '../python-env-manager';
import { getEffectiveSourcePath } from '../updater/path-resolver';

// Debug logging helper - enabled in development OR when DEBUG flag is set
const DEBUG = process.env.DEBUG === 'true' || process.env.NODE_ENV === 'development';

function debugLog(message: string, data?: unknown): void {
  if (DEBUG) {
    if (data !== undefined) {
      console.debug(`[Merge History] ${message}`, data);
    } else {
      console.debug(`[Merge History] ${message}`);
    }
  }
}

/**
 * Merge history entry structure (matches Python backend MergeHistoryEntry)
 */
export interface MergeHistoryEntry {
  merge_id: string;
  task_id: string;
  spec_name: string;
  started_at: string;
  completed_at: string | null;
  source_worktree: string;
  source_branch: string;
  target_branch: string;
  files_changed: string[];
  files_added: string[];
  files_deleted: string[];
  conflicts_resolved: MergeConflictRecord[];
  total_conflicts: number;
  auto_resolved_count: number;
  ai_resolved_count: number;
  pre_merge_commit: string;
  merge_commit: string;
  success: boolean;
  error_message: string | null;
  ai_tokens_used: number;
  duration_seconds: number;
}

/**
 * Conflict record structure
 */
export interface MergeConflictRecord {
  file_path: string;
  conflict_type: string;
  resolution_method: string;
  base_content: string;
  task_content: string;
  main_content: string;
  resolved_content: string;
  ai_reasoning: string | null;
  ai_tokens_used: number;
  resolved_at: string;
}

/**
 * Execute a Python script and return JSON result
 */
async function executePythonScript(
  scriptPath: string,
  args: string[]
): Promise<{ success: boolean; data?: unknown; error?: string }> {
  return new Promise((resolve) => {
    const pythonPath = getConfiguredPythonPath();

    debugLog('Executing Python script', {
      pythonPath,
      scriptPath,
      args
    });

    const proc = spawn(pythonPath, [scriptPath, ...args], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        debugLog('Python script failed', { code, stderr });
        resolve({
          success: false,
          error: stderr || `Process exited with code ${code}`
        });
        return;
      }

      try {
        const result = JSON.parse(stdout);
        debugLog('Python script succeeded', result);
        resolve(result);
      } catch (error) {
        debugLog('Failed to parse JSON output', { stdout, error });
        resolve({
          success: false,
          error: `Failed to parse JSON: ${error instanceof Error ? error.message : String(error)}`
        });
      }
    });

    proc.on('error', (error) => {
      debugLog('Failed to spawn Python process', error);
      resolve({
        success: false,
        error: `Failed to spawn process: ${error.message}`
      });
    });
  });
}

/**
 * Get merge history list
 */
export function registerGetMergeHistory(): void {
  ipcMain.handle(
    IPC_CHANNELS.MERGE_HISTORY_GET,
    async (_event, projectId: string): Promise<IPCResult<MergeHistoryEntry[]>> => {
      debugLog('getMergeHistory handler called', { projectId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Get the source path (handles both dev and production)
        // Note: sourcePath already points to the backend root (e.g., Resources/backend or apps/backend)
        const sourcePath = getEffectiveSourcePath();
        const scriptPath = path.join(sourcePath, 'cli', 'merge_history_json.py');

        const result = await executePythonScript(scriptPath, ['list', project.path]);

        if (!result.success) {
          return {
            success: false,
            error: result.error || 'Failed to get merge history'
          };
        }

        debugLog('Fetched merge history:', Array.isArray(result.data) ? result.data.length : 0);

        return {
          success: true,
          data: result.data as MergeHistoryEntry[]
        };
      } catch (error) {
        debugLog('Failed to get merge history:', error instanceof Error ? error.message : error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get merge history'
        };
      }
    }
  );
}

/**
 * Get a single merge by ID
 */
export function registerGetMergeDetails(): void {
  ipcMain.handle(
    IPC_CHANNELS.MERGE_HISTORY_GET_DETAILS,
    async (_event, projectId: string, mergeId: string): Promise<IPCResult<MergeHistoryEntry>> => {
      debugLog('getMergeDetails handler called', { projectId, mergeId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Get the source path (handles both dev and production)
        // Note: sourcePath already points to the backend root (e.g., Resources/backend or apps/backend)
        const sourcePath = getEffectiveSourcePath();
        const scriptPath = path.join(sourcePath, 'cli', 'merge_history_json.py');

        const result = await executePythonScript(scriptPath, ['get', project.path, mergeId]);

        if (!result.success) {
          return {
            success: false,
            error: result.error || 'Failed to get merge details'
          };
        }

        return {
          success: true,
          data: result.data as MergeHistoryEntry
        };
      } catch (error) {
        debugLog('Failed to get merge details:', error instanceof Error ? error.message : error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get merge details'
        };
      }
    }
  );
}

/**
 * Rollback a specific merge
 */
export function registerRollbackMerge(): void {
  ipcMain.handle(
    IPC_CHANNELS.MERGE_HISTORY_ROLLBACK,
    async (_event, projectId: string, mergeId: string): Promise<IPCResult<{ message: string }>> => {
      debugLog('rollbackMerge handler called', { projectId, mergeId });

      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        // Get the source path (handles both dev and production)
        // Note: sourcePath already points to the backend root (e.g., Resources/backend or apps/backend)
        const sourcePath = getEffectiveSourcePath();
        const scriptPath = path.join(sourcePath, 'cli', 'merge_history_json.py');

        const result = await executePythonScript(scriptPath, ['rollback', project.path, mergeId]);

        if (!result.success) {
          return {
            success: false,
            error: result.error || 'Failed to rollback merge'
          };
        }

        return {
          success: true,
          data: result.data as { message: string }
        };
      } catch (error) {
        debugLog('Failed to rollback merge:', error instanceof Error ? error.message : error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to rollback merge'
        };
      }
    }
  );
}

/**
 * Register all merge history handlers
 */
export function registerMergeHistoryHandlers(): void {
  registerGetMergeHistory();
  registerGetMergeDetails();
  registerRollbackMerge();
}
