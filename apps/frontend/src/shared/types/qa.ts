/**
 * QA Dashboard types for validation results visualization
 */

/**
 * Status of a QA validation criterion
 */
export type QACriterionStatus = 'passed' | 'failed' | 'pending' | 'skipped';

/**
 * Evidence captured during QA validation
 */
export interface QAValidationEvidence {
  errorMessage?: string;       // Error message if validation failed
  screenshotPath?: string;     // Path to screenshot at failure point
  screenshotBase64?: string;   // Base64 encoded screenshot for display
  logOutput?: string;          // Relevant log output
  command?: string;            // Command that was executed (if applicable)
  expectedResult?: string;     // What was expected
  actualResult?: string;       // What was actually found
}

/**
 * Result of validating a single acceptance criterion
 */
export interface QACriterionResult {
  id: string;                  // Unique identifier for this criterion
  criterionText: string;       // The acceptance criterion text from spec
  status: QACriterionStatus;   // Pass/fail/pending/skipped status
  evidence?: QAValidationEvidence;  // Evidence captured during validation
  timestamp: string;           // ISO timestamp when validated
  iterationNumber: number;     // Which iteration this result is from
}

/**
 * Status of a QA iteration
 */
export type QAIterationStatus = 'approved' | 'rejected' | 'error' | 'in_progress';

/**
 * Record of a single QA validation iteration
 */
export interface QAIterationRecord {
  iterationNumber: number;     // 1-indexed iteration number
  status: QAIterationStatus;   // Overall status of this iteration
  startedAt: string;           // ISO timestamp when iteration started
  completedAt?: string;        // ISO timestamp when iteration completed
  criteriaResults: QACriterionResult[];  // Results for each criterion
  issuesFound: number;         // Count of issues found
  issuesSummary?: string;      // Summary of issues (from QA agent)
  fixRequestPath?: string;     // Path to QA_FIX_REQUEST.md if rejected
}

/**
 * Summary statistics for QA validation
 */
export interface QAValidationSummary {
  totalCriteria: number;       // Total acceptance criteria count
  passedCriteria: number;      // Criteria that passed
  failedCriteria: number;      // Criteria that failed
  pendingCriteria: number;     // Criteria not yet validated
  skippedCriteria: number;     // Criteria that were skipped
  passRate: number;            // Percentage (0-100) of criteria passing
  totalIterations: number;     // Total QA iterations run
  lastIterationStatus: QAIterationStatus;  // Status of most recent iteration
  lastValidatedAt?: string;    // ISO timestamp of last validation
}

/**
 * Single data point for trend visualization
 */
export interface QATrendDataPoint {
  date: string;                // ISO date string (day precision)
  passRate: number;            // Pass rate percentage (0-100)
  totalTasks: number;          // Tasks validated that day
  passedTasks: number;         // Tasks that passed QA
  failedTasks: number;         // Tasks that failed QA
  avgIterationsToPass?: number; // Average iterations needed to pass
}

/**
 * Trend data for QA performance visualization
 */
export interface QATrendData {
  dataPoints: QATrendDataPoint[];  // Time series data points
  periodStart: string;         // ISO timestamp of period start
  periodEnd: string;           // ISO timestamp of period end
  overallPassRate: number;     // Overall pass rate for the period
  totalTasksValidated: number; // Total tasks validated in period
}

/**
 * Complete QA validation data for a task
 */
export interface TaskQAValidationData {
  taskId: string;              // Task ID this data belongs to
  specId: string;              // Spec ID
  summary: QAValidationSummary;  // Aggregated summary
  iterations: QAIterationRecord[];  // History of all iterations
  currentCriteriaResults: QACriterionResult[];  // Latest results for each criterion
}

/**
 * Project-wide QA trend data
 */
export interface ProjectQATrends {
  projectId: string;           // Project ID
  trendData: QATrendData;      // Trend visualization data
  recentFailures: {            // Recent failed tasks for quick reference
    taskId: string;
    taskTitle: string;
    failedAt: string;
    issuesSummary?: string;
  }[];
}
