/**
 * Decision audit trail types
 *
 * These types mirror the backend decision_audit/models.py for the agent decision
 * audit trail feature. They represent key decisions made by AI agents during builds:
 * why certain approaches were chosen, what alternatives were considered, and what
 * context influenced decisions.
 */

/**
 * Types of decisions that agents make during execution.
 * Maps to DecisionType enum in backend.
 */
export type DecisionType =
  | 'approach_chosen'      // Agent chose a specific approach
  | 'alternative_rejected' // Agent explicitly rejected an alternative
  | 'context_used'         // Agent used specific context to inform decision
  | 'pattern_followed'     // Agent followed an established pattern
  | 'file_selected'        // Agent selected specific file(s) to work with
  | 'tool_selected'        // Agent selected a specific tool
  | 'error_recovery';      // Agent recovered from an error

/**
 * Confidence level for decisions.
 * Maps to ConfidenceLevel enum in backend.
 */
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/**
 * User annotation for marking decisions as good or bad patterns.
 */
export type DecisionAnnotation = 'good_pattern' | 'bad_pattern' | null;

/**
 * Context that influenced a decision.
 * Maps to DecisionContext dataclass in backend.
 */
export interface DecisionContext {
  /** Source of the context (e.g., "graphiti_query", "file_read", "user_instruction") */
  source: string;
  /** The actual context content */
  content: string;
  /** Optional timestamp when context was retrieved */
  timestamp?: string;
  /** Additional metadata about the context */
  metadata: Record<string, unknown>;
}

/**
 * A single decision entry in the audit trail.
 * Maps to DecisionEntry dataclass in backend.
 */
export interface DecisionEntry {
  /** Unique identifier for the decision */
  id: string;
  /** ISO timestamp when the decision was made */
  timestamp: string;
  /** Type of decision */
  decision_type: DecisionType;
  /** Brief description of what was decided */
  description: string;
  /** Reasoning behind the decision */
  reasoning: string;
  /** List of alternatives that were considered */
  alternatives_considered: string[];
  /** Context that influenced the decision */
  context_used: DecisionContext[];
  /** ID of the subtask this decision relates to */
  subtask_id?: string;
  /** Phase when this decision was made (e.g., "planning", "coding", "post_session") */
  phase?: string;
  /** Confidence level of the decision */
  confidence_level: ConfidenceLevel;
  /** User annotation marking this as a good or bad pattern */
  annotation?: DecisionAnnotation;
  /** User note explaining the annotation */
  annotation_note?: string;
}

/**
 * Filter criteria for querying decisions.
 * Maps to DecisionFilter dataclass in backend.
 */
export interface DecisionFilter {
  /** Filter by decision type */
  decision_type?: DecisionType;
  /** Filter by subtask ID */
  subtask_id?: string;
  /** Filter by phase */
  phase?: string;
  /** Filter by annotation status */
  annotation?: DecisionAnnotation;
  /** Filter decisions made since this timestamp */
  since?: string;
  /** Filter decisions made until this timestamp */
  until?: string;
}

/**
 * Decision audit trail for a spec/task.
 * Container for all decisions made during a build.
 */
export interface DecisionAuditTrail {
  /** Spec ID this audit trail belongs to */
  spec_id: string;
  /** When the audit trail was created */
  created_at: string;
  /** When the audit trail was last updated */
  updated_at: string;
  /** All decisions in the audit trail */
  decisions: DecisionEntry[];
}

/**
 * Summary statistics for decisions.
 */
export interface DecisionSummary {
  /** Total number of decisions */
  total: number;
  /** Count by decision type */
  by_type: Record<DecisionType, number>;
  /** Count by phase */
  by_phase: Record<string, number>;
  /** Count by annotation */
  by_annotation: {
    good_pattern: number;
    bad_pattern: number;
    unannotated: number;
  };
}

/**
 * Request to annotate a decision.
 */
export interface DecisionAnnotationRequest {
  /** ID of the decision to annotate */
  decision_id: string;
  /** Annotation to apply */
  annotation: DecisionAnnotation;
  /** Optional note explaining the annotation */
  note?: string;
  /** Whether to save to Graphiti memory as pattern/gotcha */
  save_to_memory?: boolean;
}
