import { create } from 'zustand';
import type {
  DecisionEntry,
  DecisionFilter,
  DecisionAnnotation,
  DecisionSummary,
  DecisionType
} from '../../shared/types';

interface DecisionState {
  // Data
  decisions: DecisionEntry[];
  filter: DecisionFilter;
  isLoading: boolean;
  error: string | null;

  // Actions
  setDecisions: (decisions: DecisionEntry[]) => void;
  addDecision: (decision: DecisionEntry) => void;
  updateDecision: (decisionId: string, updates: Partial<DecisionEntry>) => void;
  setFilter: (filter: DecisionFilter) => void;
  clearFilter: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearDecisions: () => void;

  // Selectors
  getFilteredDecisions: () => DecisionEntry[];
  getDecisionsBySubtask: (subtaskId: string) => DecisionEntry[];
  getDecisionsByType: (type: DecisionType) => DecisionEntry[];
  getDecisionsByPhase: (phase: string) => DecisionEntry[];
  getDecisionSummary: () => DecisionSummary;
}

/**
 * Initial empty filter state
 */
const initialFilter: DecisionFilter = {};

/**
 * Helper to check if a decision matches the current filter
 */
function matchesFilter(decision: DecisionEntry, filter: DecisionFilter): boolean {
  // Filter by decision type
  if (filter.decision_type && decision.decision_type !== filter.decision_type) {
    return false;
  }

  // Filter by subtask ID
  if (filter.subtask_id && decision.subtask_id !== filter.subtask_id) {
    return false;
  }

  // Filter by phase
  if (filter.phase && decision.phase !== filter.phase) {
    return false;
  }

  // Filter by annotation
  if (filter.annotation !== undefined) {
    if (filter.annotation === null && decision.annotation !== undefined && decision.annotation !== null) {
      return false;
    }
    if (filter.annotation !== null && decision.annotation !== filter.annotation) {
      return false;
    }
  }

  // Filter by date range
  if (filter.since) {
    const decisionTime = new Date(decision.timestamp).getTime();
    const sinceTime = new Date(filter.since).getTime();
    if (decisionTime < sinceTime) {
      return false;
    }
  }

  if (filter.until) {
    const decisionTime = new Date(decision.timestamp).getTime();
    const untilTime = new Date(filter.until).getTime();
    if (decisionTime > untilTime) {
      return false;
    }
  }

  return true;
}

/**
 * Calculate summary statistics for decisions
 */
function calculateSummary(decisions: DecisionEntry[]): DecisionSummary {
  const summary: DecisionSummary = {
    total: decisions.length,
    by_type: {
      approach_chosen: 0,
      alternative_rejected: 0,
      context_used: 0,
      pattern_followed: 0,
      file_selected: 0,
      tool_selected: 0,
      error_recovery: 0
    },
    by_phase: {},
    by_annotation: {
      good_pattern: 0,
      bad_pattern: 0,
      unannotated: 0
    }
  };

  for (const decision of decisions) {
    // Count by type
    summary.by_type[decision.decision_type]++;

    // Count by phase
    if (decision.phase) {
      summary.by_phase[decision.phase] = (summary.by_phase[decision.phase] || 0) + 1;
    }

    // Count by annotation
    if (decision.annotation === 'good_pattern') {
      summary.by_annotation.good_pattern++;
    } else if (decision.annotation === 'bad_pattern') {
      summary.by_annotation.bad_pattern++;
    } else {
      summary.by_annotation.unannotated++;
    }
  }

  return summary;
}

export const useDecisionStore = create<DecisionState>((set, get) => ({
  // Initial state
  decisions: [],
  filter: initialFilter,
  isLoading: false,
  error: null,

  // Actions
  setDecisions: (decisions) => set({ decisions }),

  addDecision: (decision) =>
    set((state) => ({
      decisions: [...state.decisions, decision]
    })),

  updateDecision: (decisionId, updates) =>
    set((state) => ({
      decisions: state.decisions.map((d) =>
        d.id === decisionId ? { ...d, ...updates } : d
      )
    })),

  setFilter: (filter) => set({ filter }),

  clearFilter: () => set({ filter: initialFilter }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  clearDecisions: () => set({ decisions: [], filter: initialFilter, error: null }),

  // Selectors
  getFilteredDecisions: () => {
    const state = get();
    return state.decisions.filter((d) => matchesFilter(d, state.filter));
  },

  getDecisionsBySubtask: (subtaskId) => {
    const state = get();
    return state.decisions.filter((d) => d.subtask_id === subtaskId);
  },

  getDecisionsByType: (type) => {
    const state = get();
    return state.decisions.filter((d) => d.decision_type === type);
  },

  getDecisionsByPhase: (phase) => {
    const state = get();
    return state.decisions.filter((d) => d.phase === phase);
  },

  getDecisionSummary: () => {
    const state = get();
    return calculateSummary(state.decisions);
  }
}));

// Helper functions

/**
 * Load decisions for a task/spec
 * @param taskId - The task ID or spec ID to load decisions for
 */
export async function loadDecisions(taskId: string): Promise<void> {
  const store = useDecisionStore.getState();
  store.setLoading(true);
  store.setError(null);

  try {
    const result = await window.electronAPI.getDecisions(taskId);
    if (result.success && result.data) {
      store.setDecisions(result.data);
    } else {
      store.setError(result.error || 'Failed to load decisions');
      store.setDecisions([]);
    }
  } catch (error) {
    store.setError(error instanceof Error ? error.message : 'Unknown error');
    store.setDecisions([]);
  } finally {
    store.setLoading(false);
  }
}

/**
 * Annotate a decision as a good or bad pattern
 * @param taskId - The task ID the decision belongs to
 * @param decisionId - The decision ID to annotate
 * @param annotation - The annotation to apply
 * @param note - Optional note explaining the annotation
 * @param saveToMemory - Whether to save to Graphiti memory
 */
export async function annotateDecision(
  taskId: string,
  decisionId: string,
  annotation: DecisionAnnotation,
  note?: string,
  saveToMemory?: boolean
): Promise<boolean> {
  const store = useDecisionStore.getState();

  try {
    const result = await window.electronAPI.annotateDecision(taskId, {
      decision_id: decisionId,
      annotation,
      note,
      save_to_memory: saveToMemory
    });

    if (result.success) {
      // Update local state
      store.updateDecision(decisionId, {
        annotation,
        annotation_note: note
      });
      return true;
    }

    store.setError(result.error || 'Failed to annotate decision');
    return false;
  } catch (error) {
    store.setError(error instanceof Error ? error.message : 'Unknown error');
    return false;
  }
}

/**
 * Filter decisions by type
 * @param type - The decision type to filter by, or undefined to clear type filter
 */
export function filterByType(type?: DecisionType): void {
  const store = useDecisionStore.getState();
  store.setFilter({
    ...store.filter,
    decision_type: type
  });
}

/**
 * Filter decisions by subtask
 * @param subtaskId - The subtask ID to filter by, or undefined to clear subtask filter
 */
export function filterBySubtask(subtaskId?: string): void {
  const store = useDecisionStore.getState();
  store.setFilter({
    ...store.filter,
    subtask_id: subtaskId
  });
}

/**
 * Filter decisions by phase
 * @param phase - The phase to filter by, or undefined to clear phase filter
 */
export function filterByPhase(phase?: string): void {
  const store = useDecisionStore.getState();
  store.setFilter({
    ...store.filter,
    phase
  });
}

/**
 * Filter decisions by annotation status
 * @param annotation - The annotation to filter by, or undefined to clear annotation filter
 */
export function filterByAnnotation(annotation?: DecisionAnnotation): void {
  const store = useDecisionStore.getState();
  store.setFilter({
    ...store.filter,
    annotation
  });
}

/**
 * Clear all filters
 */
export function clearAllFilters(): void {
  useDecisionStore.getState().clearFilter();
}

/**
 * Get unique phases from current decisions
 */
export function getUniquePhases(): string[] {
  const decisions = useDecisionStore.getState().decisions;
  const phases = new Set<string>();

  for (const decision of decisions) {
    if (decision.phase) {
      phases.add(decision.phase);
    }
  }

  return Array.from(phases).sort();
}

/**
 * Get unique subtask IDs from current decisions
 */
export function getUniqueSubtasks(): string[] {
  const decisions = useDecisionStore.getState().decisions;
  const subtasks = new Set<string>();

  for (const decision of decisions) {
    if (decision.subtask_id) {
      subtasks.add(decision.subtask_id);
    }
  }

  return Array.from(subtasks).sort();
}
