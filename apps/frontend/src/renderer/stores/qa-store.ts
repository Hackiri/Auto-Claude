import { create } from 'zustand';
import type {
  TaskQAValidationData,
  ProjectQATrends
} from '../../shared/types';
import { debugLog } from '../../shared/utils/debug-logger';

/**
 * QA Validation Dashboard Store
 *
 * Manages state for QA validation data including:
 * - Current task's QA validation results
 * - Project-wide QA trends
 * - Loading and error states
 */

interface QAState {
  // Current task's QA validation data
  qaData: TaskQAValidationData | null;
  qaDataLoading: boolean;
  qaDataError: string | null;

  // Project-wide QA trends
  projectTrends: ProjectQATrends | null;
  trendsLoading: boolean;
  trendsError: string | null;

  // Track which task/project is currently loaded (for cache invalidation)
  currentTaskId: string | null;
  currentProjectId: string | null;

  // Actions
  setQAData: (data: TaskQAValidationData | null) => void;
  setQADataLoading: (loading: boolean) => void;
  setQADataError: (error: string | null) => void;
  setProjectTrends: (trends: ProjectQATrends | null) => void;
  setTrendsLoading: (loading: boolean) => void;
  setTrendsError: (error: string | null) => void;
  setCurrentTaskId: (taskId: string | null) => void;
  setCurrentProjectId: (projectId: string | null) => void;
  clearQAData: () => void;
}

export const useQAStore = create<QAState>((set) => ({
  // Current task's QA validation data
  qaData: null,
  qaDataLoading: false,
  qaDataError: null,

  // Project-wide QA trends
  projectTrends: null,
  trendsLoading: false,
  trendsError: null,

  // Track which task/project is currently loaded
  currentTaskId: null,
  currentProjectId: null,

  // Actions
  setQAData: (data) => set({ qaData: data }),
  setQADataLoading: (loading) => set({ qaDataLoading: loading }),
  setQADataError: (error) => set({ qaDataError: error }),
  setProjectTrends: (trends) => set({ projectTrends: trends }),
  setTrendsLoading: (loading) => set({ trendsLoading: loading }),
  setTrendsError: (error) => set({ trendsError: error }),
  setCurrentTaskId: (taskId) => set({ currentTaskId: taskId }),
  setCurrentProjectId: (projectId) => set({ currentProjectId: projectId }),
  clearQAData: () =>
    set({
      qaData: null,
      qaDataLoading: false,
      qaDataError: null,
      projectTrends: null,
      trendsLoading: false,
      trendsError: null,
      currentTaskId: null,
      currentProjectId: null
    })
}));

/**
 * Load QA validation data for a specific task
 *
 * @param projectId - The project ID containing the task
 * @param taskId - The task/spec ID to load QA data for
 */
export async function loadQAData(projectId: string, taskId: string): Promise<void> {
  const store = useQAStore.getState();

  debugLog('[QAStore] Loading QA data for task:', { projectId, taskId });

  store.setQADataLoading(true);
  store.setQADataError(null);
  store.setCurrentTaskId(taskId);

  try {
    const result = await window.electronAPI.getQAValidationData(projectId, taskId);

    if (result.success && result.data) {
      debugLog('[QAStore] QA data loaded:', {
        taskId,
        totalCriteria: result.data.summary.totalCriteria,
        passRate: result.data.summary.passRate,
        iterations: result.data.iterations.length
      });
      store.setQAData(result.data);
    } else {
      const errorMsg = result.error || 'Failed to load QA validation data';
      debugLog('[QAStore] Failed to load QA data:', errorMsg);
      store.setQADataError(errorMsg);
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Unknown error loading QA data';
    debugLog('[QAStore] Error loading QA data:', errorMsg);
    store.setQADataError(errorMsg);
  } finally {
    store.setQADataLoading(false);
  }
}

/**
 * Load project-wide QA trends
 *
 * @param projectId - The project ID to load trends for
 */
export async function loadProjectTrends(projectId: string): Promise<void> {
  const store = useQAStore.getState();

  debugLog('[QAStore] Loading project QA trends:', { projectId });

  store.setTrendsLoading(true);
  store.setTrendsError(null);
  store.setCurrentProjectId(projectId);

  try {
    const result = await window.electronAPI.getProjectQATrends(projectId);

    if (result.success && result.data) {
      debugLog('[QAStore] Project trends loaded:', {
        projectId,
        totalTasksValidated: result.data.trendData.totalTasksValidated,
        overallPassRate: result.data.trendData.overallPassRate,
        dataPoints: result.data.trendData.dataPoints.length,
        recentFailures: result.data.recentFailures.length
      });
      store.setProjectTrends(result.data);
    } else {
      const errorMsg = result.error || 'Failed to load project QA trends';
      debugLog('[QAStore] Failed to load project trends:', errorMsg);
      store.setTrendsError(errorMsg);
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : 'Unknown error loading project trends';
    debugLog('[QAStore] Error loading project trends:', errorMsg);
    store.setTrendsError(errorMsg);
  } finally {
    store.setTrendsLoading(false);
  }
}

/**
 * Clear all QA data from the store
 * Use when switching projects or tasks
 */
export function clearQAData(): void {
  debugLog('[QAStore] Clearing QA data');
  useQAStore.getState().clearQAData();
}

/**
 * Refresh QA data for the currently loaded task
 * Returns true if data was refreshed, false if no task is loaded
 */
export async function refreshQAData(): Promise<boolean> {
  const store = useQAStore.getState();
  const { currentTaskId, currentProjectId } = store;

  if (!currentTaskId || !currentProjectId) {
    debugLog('[QAStore] Cannot refresh - no task currently loaded');
    return false;
  }

  await loadQAData(currentProjectId, currentTaskId);
  return true;
}

/**
 * Check if QA data needs to be reloaded for a given task
 * Returns true if the task is different from the currently loaded one
 */
export function needsReload(taskId: string): boolean {
  const { currentTaskId } = useQAStore.getState();
  return currentTaskId !== taskId;
}
