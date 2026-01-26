/**
 * QA Validation Dashboard Handlers
 *
 * IPC handlers for retrieving QA validation data from implementation_plan.json
 * including criterion results, iteration history, and computed trend data.
 */

import { ipcMain } from 'electron';
import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { IPC_CHANNELS, getSpecsDir, AUTO_BUILD_PATHS } from '../../../shared/constants';
import type { IPCResult } from '../../../shared/types';
import type {
  TaskQAValidationData,
  QAIterationRecord,
  QACriterionResult,
  QAValidationSummary,
  QAIterationStatus,
  QACriterionStatus
} from '../../../shared/types/qa';
import { projectStore } from '../../project-store';
import { getTaskWorktreeDir } from '../../worktree-paths';

/**
 * Shape of criterion results stored in implementation_plan.json
 * (as defined by backend qa/report.py)
 */
interface StoredCriterionResult {
  criterion_id: string;
  criterion_text: string;
  status: 'passed' | 'failed' | 'pending' | 'skipped';
  evidence?: {
    error_message?: string;
    screenshot_path?: string;
    log_output?: string;
    command?: string;
    expected_result?: string;
    actual_result?: string;
  };
  timestamp: string;
  iteration_number: number;
}

/**
 * Shape of iteration records stored in implementation_plan.json
 */
interface StoredIterationRecord {
  iteration_number: number;
  status: 'approved' | 'rejected' | 'error' | 'in_progress';
  started_at: string;
  completed_at?: string;
  issues_found?: number;
  issues_summary?: string;
  fix_request_path?: string;
}

/**
 * Shape of QA data in implementation_plan.json
 */
interface ImplementationPlanQAData {
  qa_criterion_results?: StoredCriterionResult[];
  qa_iterations?: StoredIterationRecord[];
  qa_signoff?: {
    status?: string;
    timestamp?: string;
    issues?: string[];
  };
}

/**
 * Load implementation_plan.json from the appropriate location
 * (worktree or main project)
 */
function loadImplementationPlan(
  projectPath: string,
  specsBaseDir: string,
  specId: string
): ImplementationPlanQAData | null {
  // First try worktree location
  const worktreeDir = getTaskWorktreeDir(projectPath);
  const worktreePlanPath = path.join(worktreeDir, specId, specsBaseDir, specId, AUTO_BUILD_PATHS.IMPLEMENTATION_PLAN);

  if (existsSync(worktreePlanPath)) {
    try {
      const content = readFileSync(worktreePlanPath, 'utf-8');
      return JSON.parse(content);
    } catch {
      // Fall through to main project
    }
  }

  // Try main project location
  const mainPlanPath = path.join(projectPath, specsBaseDir, specId, AUTO_BUILD_PATHS.IMPLEMENTATION_PLAN);

  if (existsSync(mainPlanPath)) {
    try {
      const content = readFileSync(mainPlanPath, 'utf-8');
      return JSON.parse(content);
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Convert stored criterion result to frontend type
 */
function convertCriterionResult(stored: StoredCriterionResult): QACriterionResult {
  return {
    id: stored.criterion_id,
    criterionText: stored.criterion_text,
    status: stored.status as QACriterionStatus,
    evidence: stored.evidence ? {
      errorMessage: stored.evidence.error_message,
      screenshotPath: stored.evidence.screenshot_path,
      logOutput: stored.evidence.log_output,
      command: stored.evidence.command,
      expectedResult: stored.evidence.expected_result,
      actualResult: stored.evidence.actual_result
    } : undefined,
    timestamp: stored.timestamp,
    iterationNumber: stored.iteration_number
  };
}

/**
 * Convert stored iteration record to frontend type
 */
function convertIterationRecord(
  stored: StoredIterationRecord,
  criteriaResults: QACriterionResult[]
): QAIterationRecord {
  // Filter criteria results for this iteration
  const iterationCriteria = criteriaResults.filter(
    cr => cr.iterationNumber === stored.iteration_number
  );

  return {
    iterationNumber: stored.iteration_number,
    status: stored.status as QAIterationStatus,
    startedAt: stored.started_at,
    completedAt: stored.completed_at,
    criteriaResults: iterationCriteria,
    issuesFound: stored.issues_found ?? iterationCriteria.filter(c => c.status === 'failed').length,
    issuesSummary: stored.issues_summary,
    fixRequestPath: stored.fix_request_path
  };
}

/**
 * Compute validation summary from criterion results
 */
function computeSummary(
  criteriaResults: QACriterionResult[],
  iterations: QAIterationRecord[]
): QAValidationSummary {
  // Get latest results for each criterion (deduplicated by id)
  const latestResults = new Map<string, QACriterionResult>();
  for (const result of criteriaResults) {
    const existing = latestResults.get(result.id);
    if (!existing || result.iterationNumber > existing.iterationNumber) {
      latestResults.set(result.id, result);
    }
  }

  const currentResults = Array.from(latestResults.values());

  const totalCriteria = currentResults.length;
  const passedCriteria = currentResults.filter(c => c.status === 'passed').length;
  const failedCriteria = currentResults.filter(c => c.status === 'failed').length;
  const pendingCriteria = currentResults.filter(c => c.status === 'pending').length;
  const skippedCriteria = currentResults.filter(c => c.status === 'skipped').length;

  const passRate = totalCriteria > 0 ? (passedCriteria / totalCriteria) * 100 : 0;

  const lastIteration = iterations.length > 0
    ? iterations.reduce((a, b) => a.iterationNumber > b.iterationNumber ? a : b)
    : null;

  const lastValidatedResult = currentResults.length > 0
    ? currentResults.reduce((a, b) => new Date(a.timestamp) > new Date(b.timestamp) ? a : b)
    : null;

  return {
    totalCriteria,
    passedCriteria,
    failedCriteria,
    pendingCriteria,
    skippedCriteria,
    passRate,
    totalIterations: iterations.length,
    lastIterationStatus: lastIteration?.status ?? 'in_progress',
    lastValidatedAt: lastValidatedResult?.timestamp
  };
}

/**
 * Register QA validation dashboard IPC handlers
 */
export function registerTaskQAHandlers(): void {
  /**
   * Get QA validation data for a specific task
   * Returns criterion results, iteration history, and computed summary
   */
  ipcMain.handle(
    IPC_CHANNELS.TASK_QA_VALIDATION_GET,
    async (_, projectId: string, specId: string): Promise<IPCResult<TaskQAValidationData | null>> => {
      try {
        const project = projectStore.getProject(projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const specsBaseDir = getSpecsDir(project.autoBuildPath);
        const planData = loadImplementationPlan(project.path, specsBaseDir, specId);

        if (!planData) {
          // No plan found - return empty data structure
          return {
            success: true,
            data: {
              taskId: specId,
              specId,
              summary: {
                totalCriteria: 0,
                passedCriteria: 0,
                failedCriteria: 0,
                pendingCriteria: 0,
                skippedCriteria: 0,
                passRate: 0,
                totalIterations: 0,
                lastIterationStatus: 'in_progress'
              },
              iterations: [],
              currentCriteriaResults: []
            }
          };
        }

        // Convert stored criterion results
        const storedCriteria = planData.qa_criterion_results ?? [];
        const criteriaResults = storedCriteria.map(convertCriterionResult);

        // Convert stored iteration records
        const storedIterations = planData.qa_iterations ?? [];
        const iterations = storedIterations.map(stored =>
          convertIterationRecord(stored, criteriaResults)
        );

        // Sort iterations by number (descending for display)
        iterations.sort((a, b) => b.iterationNumber - a.iterationNumber);

        // Compute summary
        const summary = computeSummary(criteriaResults, iterations);

        // Get current (latest) criteria results
        const latestResults = new Map<string, QACriterionResult>();
        for (const result of criteriaResults) {
          const existing = latestResults.get(result.id);
          if (!existing || result.iterationNumber > existing.iterationNumber) {
            latestResults.set(result.id, result);
          }
        }

        const qaData: TaskQAValidationData = {
          taskId: specId,
          specId,
          summary,
          iterations,
          currentCriteriaResults: Array.from(latestResults.values())
        };

        return { success: true, data: qaData };
      } catch (error) {
        console.error('[QA Handlers] Failed to get QA validation data:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get QA validation data'
        };
      }
    }
  );
}
