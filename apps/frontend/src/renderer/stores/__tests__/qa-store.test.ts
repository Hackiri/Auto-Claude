/**
 * Unit tests for QA Store
 * Tests Zustand store for QA validation data state management
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useQAStore, loadQAData, loadProjectTrends, clearQAData, refreshQAData, needsReload } from '../qa-store';
import type {
  TaskQAValidationData,
  ProjectQATrends,
  QACriterionResult,
  QAIterationRecord,
  QATrendDataPoint,
  ElectronAPI
} from '../../../shared/types';

// Mock debug-logger to prevent console output during tests
vi.mock('../../../shared/utils/debug-logger', () => ({
  debugLog: vi.fn(),
  debugError: vi.fn()
}));

// Helper to create test QA validation data
function createTestQAData(overrides: Partial<TaskQAValidationData> = {}): TaskQAValidationData {
  const criteriaResult: QACriterionResult = {
    id: 'criterion-1',
    criterionText: 'Test criterion',
    status: 'passed',
    timestamp: new Date().toISOString(),
    iterationNumber: 1
  };

  const iterationRecord: QAIterationRecord = {
    iterationNumber: 1,
    status: 'approved',
    startedAt: new Date().toISOString(),
    completedAt: new Date().toISOString(),
    criteriaResults: [criteriaResult],
    issuesFound: 0
  };

  return {
    taskId: 'task-001',
    specId: 'spec-001',
    summary: {
      totalCriteria: 5,
      passedCriteria: 4,
      failedCriteria: 1,
      pendingCriteria: 0,
      skippedCriteria: 0,
      passRate: 80,
      totalIterations: 2,
      lastIterationStatus: 'approved',
      lastValidatedAt: new Date().toISOString()
    },
    iterations: [iterationRecord],
    currentCriteriaResults: [criteriaResult],
    ...overrides
  };
}

// Helper to create test project trends data
function createTestProjectTrends(overrides: Partial<ProjectQATrends> = {}): ProjectQATrends {
  const dataPoint: QATrendDataPoint = {
    date: new Date().toISOString().split('T')[0],
    passRate: 85,
    totalTasks: 10,
    passedTasks: 8,
    failedTasks: 2,
    avgIterationsToPass: 1.5
  };

  return {
    projectId: 'project-001',
    trendData: {
      dataPoints: [dataPoint],
      periodStart: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
      periodEnd: new Date().toISOString(),
      overallPassRate: 85,
      totalTasksValidated: 10
    },
    recentFailures: [
      {
        taskId: 'task-failed-1',
        taskTitle: 'Failed Task 1',
        failedAt: new Date().toISOString(),
        issuesSummary: 'Test failures found'
      }
    ],
    ...overrides
  };
}

// Mock electronAPI
const mockGetQAValidationData = vi.fn();
const mockGetProjectQATrends = vi.fn();

describe('QA Store', () => {
  beforeEach(() => {
    // Reset store to initial state
    useQAStore.setState({
      qaData: null,
      qaDataLoading: false,
      qaDataError: null,
      projectTrends: null,
      trendsLoading: false,
      trendsError: null,
      currentTaskId: null,
      currentProjectId: null
    });

    // Setup mock electronAPI
    (window as Window & { electronAPI: unknown }).electronAPI = {
      getQAValidationData: mockGetQAValidationData,
      getProjectQATrends: mockGetProjectQATrends
    } as unknown as ElectronAPI;

    // Reset mocks
    mockGetQAValidationData.mockReset();
    mockGetProjectQATrends.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Store State Actions', () => {
    describe('setQAData', () => {
      it('should set QA data', () => {
        const testData = createTestQAData();

        useQAStore.getState().setQAData(testData);

        expect(useQAStore.getState().qaData).toEqual(testData);
      });

      it('should clear QA data with null', () => {
        useQAStore.setState({ qaData: createTestQAData() });

        useQAStore.getState().setQAData(null);

        expect(useQAStore.getState().qaData).toBeNull();
      });
    });

    describe('setQADataLoading', () => {
      it('should set loading state to true', () => {
        useQAStore.getState().setQADataLoading(true);

        expect(useQAStore.getState().qaDataLoading).toBe(true);
      });

      it('should set loading state to false', () => {
        useQAStore.setState({ qaDataLoading: true });

        useQAStore.getState().setQADataLoading(false);

        expect(useQAStore.getState().qaDataLoading).toBe(false);
      });
    });

    describe('setQADataError', () => {
      it('should set error message', () => {
        useQAStore.getState().setQADataError('Test error');

        expect(useQAStore.getState().qaDataError).toBe('Test error');
      });

      it('should clear error with null', () => {
        useQAStore.setState({ qaDataError: 'Previous error' });

        useQAStore.getState().setQADataError(null);

        expect(useQAStore.getState().qaDataError).toBeNull();
      });
    });

    describe('setProjectTrends', () => {
      it('should set project trends data', () => {
        const trends = createTestProjectTrends();

        useQAStore.getState().setProjectTrends(trends);

        expect(useQAStore.getState().projectTrends).toEqual(trends);
      });

      it('should clear trends with null', () => {
        useQAStore.setState({ projectTrends: createTestProjectTrends() });

        useQAStore.getState().setProjectTrends(null);

        expect(useQAStore.getState().projectTrends).toBeNull();
      });
    });

    describe('setTrendsLoading', () => {
      it('should set trends loading state', () => {
        useQAStore.getState().setTrendsLoading(true);

        expect(useQAStore.getState().trendsLoading).toBe(true);
      });
    });

    describe('setTrendsError', () => {
      it('should set trends error message', () => {
        useQAStore.getState().setTrendsError('Trends error');

        expect(useQAStore.getState().trendsError).toBe('Trends error');
      });
    });

    describe('setCurrentTaskId', () => {
      it('should set current task ID', () => {
        useQAStore.getState().setCurrentTaskId('task-123');

        expect(useQAStore.getState().currentTaskId).toBe('task-123');
      });
    });

    describe('setCurrentProjectId', () => {
      it('should set current project ID', () => {
        useQAStore.getState().setCurrentProjectId('project-123');

        expect(useQAStore.getState().currentProjectId).toBe('project-123');
      });
    });

    describe('clearQAData', () => {
      it('should clear all QA state', () => {
        // Set up initial state with data
        useQAStore.setState({
          qaData: createTestQAData(),
          qaDataLoading: true,
          qaDataError: 'some error',
          projectTrends: createTestProjectTrends(),
          trendsLoading: true,
          trendsError: 'trends error',
          currentTaskId: 'task-1',
          currentProjectId: 'project-1'
        });

        useQAStore.getState().clearQAData();

        const state = useQAStore.getState();
        expect(state.qaData).toBeNull();
        expect(state.qaDataLoading).toBe(false);
        expect(state.qaDataError).toBeNull();
        expect(state.projectTrends).toBeNull();
        expect(state.trendsLoading).toBe(false);
        expect(state.trendsError).toBeNull();
        expect(state.currentTaskId).toBeNull();
        expect(state.currentProjectId).toBeNull();
      });
    });
  });

  describe('loadQAData', () => {
    it('should load QA data successfully', async () => {
      const testData = createTestQAData({ taskId: 'task-abc', specId: '001-feature' });
      mockGetQAValidationData.mockResolvedValue({
        success: true,
        data: testData
      });

      await loadQAData('project-1', 'task-abc');

      const state = useQAStore.getState();
      expect(state.qaData).toEqual(testData);
      expect(state.qaDataLoading).toBe(false);
      expect(state.qaDataError).toBeNull();
      expect(state.currentTaskId).toBe('task-abc');
      expect(mockGetQAValidationData).toHaveBeenCalledWith('project-1', 'task-abc');
    });

    it('should set loading state during fetch', async () => {
      // Create a promise that we can control
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      mockGetQAValidationData.mockReturnValue(pendingPromise);

      // Start loading (don't await)
      const loadPromise = loadQAData('project-1', 'task-1');

      // Check loading state is set
      expect(useQAStore.getState().qaDataLoading).toBe(true);
      expect(useQAStore.getState().currentTaskId).toBe('task-1');

      // Resolve and complete
      resolvePromise!({ success: true, data: createTestQAData() });
      await loadPromise;

      expect(useQAStore.getState().qaDataLoading).toBe(false);
    });

    it('should handle API error response', async () => {
      mockGetQAValidationData.mockResolvedValue({
        success: false,
        error: 'QA data not found'
      });

      await loadQAData('project-1', 'task-nonexistent');

      const state = useQAStore.getState();
      expect(state.qaData).toBeNull();
      expect(state.qaDataLoading).toBe(false);
      expect(state.qaDataError).toBe('QA data not found');
    });

    it('should handle API error response with no error message', async () => {
      mockGetQAValidationData.mockResolvedValue({
        success: false
      });

      await loadQAData('project-1', 'task-1');

      const state = useQAStore.getState();
      expect(state.qaDataError).toBe('Failed to load QA validation data');
    });

    it('should handle exception during fetch', async () => {
      mockGetQAValidationData.mockRejectedValue(new Error('Network error'));

      await loadQAData('project-1', 'task-1');

      const state = useQAStore.getState();
      expect(state.qaData).toBeNull();
      expect(state.qaDataLoading).toBe(false);
      expect(state.qaDataError).toBe('Network error');
    });

    it('should handle non-Error exception', async () => {
      mockGetQAValidationData.mockRejectedValue('String error');

      await loadQAData('project-1', 'task-1');

      const state = useQAStore.getState();
      expect(state.qaDataError).toBe('Unknown error loading QA data');
    });

    it('should clear previous error before loading', async () => {
      useQAStore.setState({ qaDataError: 'Previous error' });
      mockGetQAValidationData.mockResolvedValue({
        success: true,
        data: createTestQAData()
      });

      await loadQAData('project-1', 'task-1');

      expect(useQAStore.getState().qaDataError).toBeNull();
    });

    it('should handle null data in success response', async () => {
      mockGetQAValidationData.mockResolvedValue({
        success: true,
        data: null
      });

      await loadQAData('project-1', 'task-1');

      const state = useQAStore.getState();
      // When success is true but data is null, it should set error
      expect(state.qaDataError).toBe('Failed to load QA validation data');
    });
  });

  describe('loadProjectTrends', () => {
    it('should load project trends successfully', async () => {
      const testTrends = createTestProjectTrends({ projectId: 'project-xyz' });
      mockGetProjectQATrends.mockResolvedValue({
        success: true,
        data: testTrends
      });

      await loadProjectTrends('project-xyz');

      const state = useQAStore.getState();
      expect(state.projectTrends).toEqual(testTrends);
      expect(state.trendsLoading).toBe(false);
      expect(state.trendsError).toBeNull();
      expect(state.currentProjectId).toBe('project-xyz');
      expect(mockGetProjectQATrends).toHaveBeenCalledWith('project-xyz');
    });

    it('should set loading state during fetch', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      mockGetProjectQATrends.mockReturnValue(pendingPromise);

      const loadPromise = loadProjectTrends('project-1');

      expect(useQAStore.getState().trendsLoading).toBe(true);
      expect(useQAStore.getState().currentProjectId).toBe('project-1');

      resolvePromise!({ success: true, data: createTestProjectTrends() });
      await loadPromise;

      expect(useQAStore.getState().trendsLoading).toBe(false);
    });

    it('should handle API error response', async () => {
      mockGetProjectQATrends.mockResolvedValue({
        success: false,
        error: 'Project not found'
      });

      await loadProjectTrends('project-nonexistent');

      const state = useQAStore.getState();
      expect(state.projectTrends).toBeNull();
      expect(state.trendsLoading).toBe(false);
      expect(state.trendsError).toBe('Project not found');
    });

    it('should handle API error response with no error message', async () => {
      mockGetProjectQATrends.mockResolvedValue({
        success: false
      });

      await loadProjectTrends('project-1');

      const state = useQAStore.getState();
      expect(state.trendsError).toBe('Failed to load project QA trends');
    });

    it('should handle exception during fetch', async () => {
      mockGetProjectQATrends.mockRejectedValue(new Error('Database connection failed'));

      await loadProjectTrends('project-1');

      const state = useQAStore.getState();
      expect(state.projectTrends).toBeNull();
      expect(state.trendsLoading).toBe(false);
      expect(state.trendsError).toBe('Database connection failed');
    });

    it('should handle non-Error exception', async () => {
      mockGetProjectQATrends.mockRejectedValue({ code: 500 });

      await loadProjectTrends('project-1');

      const state = useQAStore.getState();
      expect(state.trendsError).toBe('Unknown error loading project trends');
    });

    it('should clear previous error before loading', async () => {
      useQAStore.setState({ trendsError: 'Previous trends error' });
      mockGetProjectQATrends.mockResolvedValue({
        success: true,
        data: createTestProjectTrends()
      });

      await loadProjectTrends('project-1');

      expect(useQAStore.getState().trendsError).toBeNull();
    });

    it('should handle null data in success response', async () => {
      mockGetProjectQATrends.mockResolvedValue({
        success: true,
        data: null
      });

      await loadProjectTrends('project-1');

      const state = useQAStore.getState();
      expect(state.trendsError).toBe('Failed to load project QA trends');
    });
  });

  describe('clearQAData (exported function)', () => {
    it('should clear all QA data via exported function', () => {
      useQAStore.setState({
        qaData: createTestQAData(),
        projectTrends: createTestProjectTrends(),
        currentTaskId: 'task-1',
        currentProjectId: 'project-1'
      });

      clearQAData();

      const state = useQAStore.getState();
      expect(state.qaData).toBeNull();
      expect(state.projectTrends).toBeNull();
      expect(state.currentTaskId).toBeNull();
      expect(state.currentProjectId).toBeNull();
    });
  });

  describe('refreshQAData', () => {
    it('should refresh QA data for currently loaded task', async () => {
      useQAStore.setState({
        currentTaskId: 'task-refresh',
        currentProjectId: 'project-refresh'
      });

      const freshData = createTestQAData({ taskId: 'task-refresh' });
      mockGetQAValidationData.mockResolvedValue({
        success: true,
        data: freshData
      });

      const result = await refreshQAData();

      expect(result).toBe(true);
      expect(mockGetQAValidationData).toHaveBeenCalledWith('project-refresh', 'task-refresh');
      expect(useQAStore.getState().qaData).toEqual(freshData);
    });

    it('should return false when no task is loaded', async () => {
      useQAStore.setState({
        currentTaskId: null,
        currentProjectId: 'project-1'
      });

      const result = await refreshQAData();

      expect(result).toBe(false);
      expect(mockGetQAValidationData).not.toHaveBeenCalled();
    });

    it('should return false when no project is loaded', async () => {
      useQAStore.setState({
        currentTaskId: 'task-1',
        currentProjectId: null
      });

      const result = await refreshQAData();

      expect(result).toBe(false);
      expect(mockGetQAValidationData).not.toHaveBeenCalled();
    });

    it('should return false when neither task nor project is loaded', async () => {
      useQAStore.setState({
        currentTaskId: null,
        currentProjectId: null
      });

      const result = await refreshQAData();

      expect(result).toBe(false);
    });
  });

  describe('needsReload', () => {
    it('should return true when task ID is different', () => {
      useQAStore.setState({ currentTaskId: 'task-1' });

      const result = needsReload('task-2');

      expect(result).toBe(true);
    });

    it('should return false when task ID is the same', () => {
      useQAStore.setState({ currentTaskId: 'task-same' });

      const result = needsReload('task-same');

      expect(result).toBe(false);
    });

    it('should return true when no task is currently loaded', () => {
      useQAStore.setState({ currentTaskId: null });

      const result = needsReload('task-new');

      expect(result).toBe(true);
    });
  });
});
