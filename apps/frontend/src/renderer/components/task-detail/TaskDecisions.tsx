import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Loader2,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  XCircle,
  FileText,
  Wrench,
  AlertTriangle,
  GitBranch,
  ThumbsUp,
  ThumbsDown,
  Filter,
  RefreshCw,
  Info,
  Zap,
  Brain
} from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../ui/collapsible';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../ui/select';
import { cn } from '../../lib/utils';
import {
  useDecisionStore,
  loadDecisions,
  annotateDecision,
  filterByType,
  filterByPhase,
  clearAllFilters,
  getUniquePhases
} from '../../stores/decision-store';
import type { Task } from '../../../shared/types';
import type { DecisionEntry, DecisionType, DecisionAnnotation, ConfidenceLevel } from '../../../shared/types/decisions';

interface TaskDecisionsProps {
  task: Task;
}

// Decision type labels for display
const DECISION_TYPE_LABELS: Record<DecisionType, string> = {
  approach_chosen: 'Approach Chosen',
  alternative_rejected: 'Alternative Rejected',
  context_used: 'Context Used',
  pattern_followed: 'Pattern Followed',
  file_selected: 'File Selected',
  tool_selected: 'Tool Selected',
  error_recovery: 'Error Recovery'
};

// Decision type icons
const DECISION_TYPE_ICONS: Record<DecisionType, typeof Lightbulb> = {
  approach_chosen: Lightbulb,
  alternative_rejected: XCircle,
  context_used: FileText,
  pattern_followed: GitBranch,
  file_selected: FileText,
  tool_selected: Wrench,
  error_recovery: AlertTriangle
};

// Decision type colors
const DECISION_TYPE_COLORS: Record<DecisionType, string> = {
  approach_chosen: 'text-success bg-success/10 border-success/30',
  alternative_rejected: 'text-destructive bg-destructive/10 border-destructive/30',
  context_used: 'text-info bg-info/10 border-info/30',
  pattern_followed: 'text-purple-500 bg-purple-500/10 border-purple-500/30',
  file_selected: 'text-amber-500 bg-amber-500/10 border-amber-500/30',
  tool_selected: 'text-cyan-500 bg-cyan-500/10 border-cyan-500/30',
  error_recovery: 'text-warning bg-warning/10 border-warning/30'
};

// Confidence level colors
const CONFIDENCE_COLORS: Record<ConfidenceLevel, string> = {
  high: 'text-success',
  medium: 'text-warning',
  low: 'text-destructive'
};

export function TaskDecisions({ task }: TaskDecisionsProps) {
  const { t } = useTranslation('tasks');
  const decisions = useDecisionStore((state) => state.decisions);
  const filter = useDecisionStore((state) => state.filter);
  const isLoading = useDecisionStore((state) => state.isLoading);
  const error = useDecisionStore((state) => state.error);
  const getFilteredDecisions = useDecisionStore((state) => state.getFilteredDecisions);

  const [expandedDecisions, setExpandedDecisions] = useState<Set<string>>(new Set());
  const [annotatingId, setAnnotatingId] = useState<string | null>(null);

  // Load decisions when task changes
  useEffect(() => {
    if (task.id) {
      loadDecisions(task.id);
    }
    // Clear expanded state when task changes
    setExpandedDecisions(new Set());
  }, [task.id]);

  // Get filtered decisions
  const filteredDecisions = useMemo(() => getFilteredDecisions(), [getFilteredDecisions, decisions, filter]);

  // Get unique phases for filter dropdown
  const uniquePhases = useMemo(() => getUniquePhases(), [decisions]);

  // Group decisions by phase
  const decisionsByPhase = useMemo(() => {
    const grouped: Record<string, DecisionEntry[]> = {};
    for (const decision of filteredDecisions) {
      const phase = decision.phase || 'unknown';
      if (!grouped[phase]) {
        grouped[phase] = [];
      }
      grouped[phase].push(decision);
    }
    return grouped;
  }, [filteredDecisions]);

  // Toggle decision expansion
  const toggleDecision = (id: string) => {
    setExpandedDecisions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Handle annotation
  const handleAnnotate = async (decisionId: string, annotation: DecisionAnnotation) => {
    setAnnotatingId(decisionId);
    try {
      await annotateDecision(task.id, decisionId, annotation, undefined, false);
    } finally {
      setAnnotatingId(null);
    }
  };

  // Handle refresh
  const handleRefresh = () => {
    if (task.id) {
      loadDecisions(task.id);
    }
  };

  // Handle filter changes
  const handleTypeFilterChange = (value: string) => {
    if (value === 'all') {
      filterByType(undefined);
    } else {
      filterByType(value as DecisionType);
    }
  };

  const handlePhaseFilterChange = (value: string) => {
    if (value === 'all') {
      filterByPhase(undefined);
    } else {
      filterByPhase(value);
    }
  };

  const handleClearFilters = () => {
    clearAllFilters();
  };

  // Check if any filters are active
  const hasActiveFilters = filter.decision_type || filter.phase || filter.subtask_id || filter.annotation;

  return (
    <div className="h-full overflow-y-auto scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
      <div className="p-4 space-y-4">
        {/* Header with filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Type filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Select value={filter.decision_type || 'all'} onValueChange={handleTypeFilterChange}>
              <SelectTrigger className="h-8 w-[160px] text-xs">
                <SelectValue placeholder={t('decisions.filterByType', 'Filter by type')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('decisions.allTypes', 'All Types')}</SelectItem>
                {(Object.keys(DECISION_TYPE_LABELS) as DecisionType[]).map((type) => (
                  <SelectItem key={type} value={type}>
                    {t(`decisions.types.${type}`, DECISION_TYPE_LABELS[type])}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Phase filter */}
          {uniquePhases.length > 0 && (
            <Select value={filter.phase || 'all'} onValueChange={handlePhaseFilterChange}>
              <SelectTrigger className="h-8 w-[140px] text-xs">
                <SelectValue placeholder={t('decisions.filterByPhase', 'Filter by phase')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('decisions.allPhases', 'All Phases')}</SelectItem>
                {uniquePhases.map((phase) => (
                  <SelectItem key={phase} value={phase}>
                    {phase}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Clear filters button */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearFilters}
              className="h-8 text-xs text-muted-foreground hover:text-foreground"
            >
              {t('decisions.clearFilters', 'Clear filters')}
            </Button>
          )}

          {/* Refresh button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isLoading}
            className="h-8 w-8 ml-auto"
            title={t('decisions.refresh', 'Refresh decisions')}
          >
            <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          </Button>
        </div>

        {/* Decision count summary */}
        {!isLoading && decisions.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {filteredDecisions.length === decisions.length
              ? t('decisions.count', '{{count}} decisions', { count: decisions.length })
              : t('decisions.filteredCount', '{{filtered}} of {{total}} decisions', {
                  filtered: filteredDecisions.length,
                  total: decisions.length
                })}
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && decisions.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            <Brain className="mx-auto mb-2 h-8 w-8 opacity-50" />
            <p>{t('decisions.empty', 'No decisions yet')}</p>
            <p className="text-xs mt-1">
              {t('decisions.emptyHint', 'Decisions will appear here as the AI makes choices during the build')}
            </p>
          </div>
        )}

        {/* Empty filtered state */}
        {!isLoading && !error && decisions.length > 0 && filteredDecisions.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            <Filter className="mx-auto mb-2 h-8 w-8 opacity-50" />
            <p>{t('decisions.noMatch', 'No decisions match your filters')}</p>
            <Button
              variant="link"
              size="sm"
              onClick={handleClearFilters}
              className="mt-2"
            >
              {t('decisions.clearFilters', 'Clear filters')}
            </Button>
          </div>
        )}

        {/* Decisions grouped by phase */}
        {!isLoading && filteredDecisions.length > 0 && (
          <div className="space-y-4">
            {Object.entries(decisionsByPhase).map(([phase, phaseDecisions]) => (
              <PhaseSection
                key={phase}
                phase={phase}
                decisions={phaseDecisions}
                expandedDecisions={expandedDecisions}
                onToggleDecision={toggleDecision}
                onAnnotate={handleAnnotate}
                annotatingId={annotatingId}
                taskId={task.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Phase Section Component
interface PhaseSectionProps {
  phase: string;
  decisions: DecisionEntry[];
  expandedDecisions: Set<string>;
  onToggleDecision: (id: string) => void;
  onAnnotate: (decisionId: string, annotation: DecisionAnnotation) => void;
  annotatingId: string | null;
  taskId: string;
}

function PhaseSection({
  phase,
  decisions,
  expandedDecisions,
  onToggleDecision,
  onAnnotate,
  annotatingId
}: PhaseSectionProps) {
  const { t } = useTranslation('tasks');
  const [isExpanded, setIsExpanded] = useState(true);

  const phaseLabel = phase === 'unknown'
    ? t('decisions.unknownPhase', 'Unknown Phase')
    : phase;

  return (
    <div className="space-y-2">
      {/* Phase header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <span className="capitalize">{phaseLabel}</span>
        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
          {decisions.length}
        </Badge>
      </button>

      {/* Phase decisions */}
      {isExpanded && (
        <div className="ml-6 space-y-2">
          {decisions.map((decision) => (
            <DecisionCard
              key={decision.id}
              decision={decision}
              isExpanded={expandedDecisions.has(decision.id)}
              onToggle={() => onToggleDecision(decision.id)}
              onAnnotate={(annotation) => onAnnotate(decision.id, annotation)}
              isAnnotating={annotatingId === decision.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Decision Card Component
interface DecisionCardProps {
  decision: DecisionEntry;
  isExpanded: boolean;
  onToggle: () => void;
  onAnnotate: (annotation: DecisionAnnotation) => void;
  isAnnotating: boolean;
}

function DecisionCard({ decision, isExpanded, onToggle, onAnnotate, isAnnotating }: DecisionCardProps) {
  const { t } = useTranslation('tasks');
  const Icon = DECISION_TYPE_ICONS[decision.decision_type];
  const typeColor = DECISION_TYPE_COLORS[decision.decision_type];

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <div
        className={cn(
          'rounded-lg border transition-colors',
          decision.annotation === 'good_pattern' && 'border-success/50 bg-success/5',
          decision.annotation === 'bad_pattern' && 'border-destructive/50 bg-destructive/5',
          !decision.annotation && 'border-border bg-card'
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="w-full flex items-start gap-3 p-3 text-left hover:bg-secondary/50 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2 shrink-0 mt-0.5">
              {isExpanded ? (
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
              )}
              <div className={cn('p-1 rounded', typeColor.split(' ').slice(1).join(' '))}>
                <Icon className={cn('h-3 w-3', typeColor.split(' ')[0])} />
              </div>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge
                  variant="outline"
                  className={cn('text-[10px] px-1.5 py-0', typeColor)}
                >
                  {t(`decisions.types.${decision.decision_type}`, DECISION_TYPE_LABELS[decision.decision_type])}
                </Badge>
                <span className="text-[10px] text-muted-foreground tabular-nums">
                  {formatTime(decision.timestamp)}
                </span>
                {decision.confidence_level && (
                  <span className={cn('text-[10px]', CONFIDENCE_COLORS[decision.confidence_level])}>
                    <Zap className="h-2.5 w-2.5 inline mr-0.5" />
                    {decision.confidence_level}
                  </span>
                )}
                {decision.annotation && (
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-[10px] px-1.5 py-0',
                      decision.annotation === 'good_pattern'
                        ? 'bg-success/10 text-success border-success/30'
                        : 'bg-destructive/10 text-destructive border-destructive/30'
                    )}
                  >
                    {decision.annotation === 'good_pattern' ? (
                      <><ThumbsUp className="h-2.5 w-2.5 inline mr-0.5" /> {t('decisions.goodPattern', 'Good')}</>
                    ) : (
                      <><ThumbsDown className="h-2.5 w-2.5 inline mr-0.5" /> {t('decisions.badPattern', 'Bad')}</>
                    )}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-foreground mt-1 line-clamp-2">
                {decision.description}
              </p>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-3 space-y-3 border-t border-border/50 mt-1 pt-3">
            {/* Reasoning */}
            {decision.reasoning && (
              <div>
                <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                  <Brain className="h-3 w-3" />
                  {t('decisions.reasoning', 'Reasoning')}
                </div>
                <p className="text-sm text-foreground">
                  {decision.reasoning}
                </p>
              </div>
            )}

            {/* Alternatives considered */}
            {decision.alternatives_considered && decision.alternatives_considered.length > 0 && (
              <div>
                <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                  <GitBranch className="h-3 w-3" />
                  {t('decisions.alternatives', 'Alternatives Considered')}
                </div>
                <ul className="space-y-1">
                  {decision.alternatives_considered.map((alt, idx) => (
                    <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                      <span className="text-muted-foreground/50 shrink-0">•</span>
                      <span>{alt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Context used */}
            {decision.context_used && decision.context_used.length > 0 && (
              <div>
                <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                  <Info className="h-3 w-3" />
                  {t('decisions.context', 'Context')}
                </div>
                <div className="space-y-1">
                  {decision.context_used.map((ctx, idx) => (
                    <div
                      key={idx}
                      className="text-xs bg-secondary/50 rounded px-2 py-1"
                    >
                      <span className="text-muted-foreground">{ctx.source}:</span>{' '}
                      <span className="text-foreground">{ctx.content}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Subtask ID */}
            {decision.subtask_id && (
              <div className="text-xs text-muted-foreground">
                {t('decisions.subtask', 'Subtask')}: {decision.subtask_id}
              </div>
            )}

            {/* Annotation note */}
            {decision.annotation_note && (
              <div className="text-xs text-muted-foreground italic">
                {t('decisions.note', 'Note')}: {decision.annotation_note}
              </div>
            )}

            {/* Annotation buttons */}
            <div className="flex items-center gap-2 pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground">
                {t('decisions.markAs', 'Mark as:')}
              </span>
              <Button
                variant={decision.annotation === 'good_pattern' ? 'default' : 'outline'}
                size="sm"
                className="h-6 text-xs px-2"
                onClick={(e) => {
                  e.stopPropagation();
                  onAnnotate(decision.annotation === 'good_pattern' ? null : 'good_pattern');
                }}
                disabled={isAnnotating}
              >
                {isAnnotating ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <>
                    <ThumbsUp className="h-3 w-3 mr-1" />
                    {t('decisions.good', 'Good Pattern')}
                  </>
                )}
              </Button>
              <Button
                variant={decision.annotation === 'bad_pattern' ? 'destructive' : 'outline'}
                size="sm"
                className="h-6 text-xs px-2"
                onClick={(e) => {
                  e.stopPropagation();
                  onAnnotate(decision.annotation === 'bad_pattern' ? null : 'bad_pattern');
                }}
                disabled={isAnnotating}
              >
                {isAnnotating ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <>
                    <ThumbsDown className="h-3 w-3 mr-1" />
                    {t('decisions.bad', 'Bad Pattern')}
                  </>
                )}
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
