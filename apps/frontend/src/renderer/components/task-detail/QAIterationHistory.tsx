import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  History,
  Loader2,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileCheck,
  ListChecks
} from 'lucide-react';
import { ScrollArea } from '../ui/scroll-area';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { cn } from '../../lib/utils';
import type { QAIterationRecord, QAIterationStatus } from '../../../shared/types';

interface QAIterationHistoryProps {
  iterations: QAIterationRecord[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

// Format date to relative time (e.g., "2 hours ago")
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  } else if (diffHours > 0) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  } else if (diffMins > 0) {
    return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  } else {
    return 'just now';
  }
}

// Format date to readable string (e.g., "Jan 1, 2024 12:00 PM")
function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
}

// Calculate duration between two timestamps
function formatDuration(startedAt: string, completedAt?: string): string {
  const start = new Date(startedAt);
  const end = completedAt ? new Date(completedAt) : new Date();
  const diffMs = end.getTime() - start.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const mins = Math.floor(diffSecs / 60);
  const secs = diffSecs % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

// Get icon for iteration status
function getStatusIcon(status: QAIterationStatus) {
  switch (status) {
    case 'approved':
      return <CheckCircle2 className="h-5 w-5 text-success" />;
    case 'rejected':
      return <XCircle className="h-5 w-5 text-destructive" />;
    case 'error':
      return <AlertTriangle className="h-5 w-5 text-warning" />;
    case 'in_progress':
      return <Loader2 className="h-5 w-5 text-info animate-spin" />;
    default:
      return <AlertCircle className="h-5 w-5 text-muted-foreground" />;
  }
}

// Get badge variant for iteration status
function getStatusBadgeVariant(status: QAIterationStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'approved':
      return 'default';
    case 'rejected':
      return 'destructive';
    case 'error':
      return 'secondary';
    case 'in_progress':
      return 'outline';
    default:
      return 'outline';
  }
}

export function QAIterationHistory({
  iterations,
  isLoading = false,
  error = null,
  onRetry
}: QAIterationHistoryProps) {
  const { t } = useTranslation(['tasks']);

  // State for expanded iteration entries
  const [expandedIterations, setExpandedIterations] = useState<Set<number>>(new Set());

  // Toggle iteration expansion
  const toggleIteration = useCallback((iterationNumber: number) => {
    setExpandedIterations(prev => {
      const next = new Set(prev);
      if (next.has(iterationNumber)) {
        next.delete(iterationNumber);
      } else {
        next.add(iterationNumber);
      }
      return next;
    });
  }, []);

  // Render loading state
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center py-12">
          <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-muted-foreground" />
          <p className="text-sm font-medium text-muted-foreground">
            {t('tasks:qa.dashboard.loading')}
          </p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center py-12">
          <AlertCircle className="h-10 w-10 mx-auto mb-3 text-destructive" />
          <p className="text-sm font-medium text-destructive mb-1">
            {t('tasks:qa.dashboard.errorLoading')}
          </p>
          <p className="text-xs text-muted-foreground mb-4">{error}</p>
          {onRetry && (
            <Button onClick={onRetry} size="sm" variant="outline">
              {t('tasks:qa.dashboard.retry')}
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Render empty state
  if (!iterations || iterations.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center py-12">
          <History className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm font-medium text-muted-foreground mb-1">
            {t('tasks:qa.history.noHistory')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('tasks:qa.history.noHistoryDescription')}
          </p>
        </div>
      </div>
    );
  }

  // Sort iterations by iteration number descending (most recent first)
  const sortedIterations = [...iterations].sort((a, b) => b.iterationNumber - a.iterationNumber);

  // Render iteration history list
  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-2">
        {/* Header with count */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <History className="h-4 w-4" />
            {t('tasks:qa.history.title')}
          </h3>
          <Badge variant="outline" className="text-xs">
            {iterations.length} {iterations.length === 1 ? 'iteration' : 'iterations'}
          </Badge>
        </div>

        {sortedIterations.map((iteration, index) => (
          <IterationEntryItem
            key={iteration.iterationNumber}
            iteration={iteration}
            isLatest={index === 0}
            isExpanded={expandedIterations.has(iteration.iterationNumber)}
            onToggle={() => toggleIteration(iteration.iterationNumber)}
          />
        ))}
      </div>
    </ScrollArea>
  );
}

// Individual iteration entry component
interface IterationEntryItemProps {
  iteration: QAIterationRecord;
  isLatest: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}

function IterationEntryItem({ iteration, isLatest, isExpanded, onToggle }: IterationEntryItemProps) {
  const { t } = useTranslation(['tasks']);

  // Calculate criteria stats
  const passedCount = iteration.criteriaResults?.filter(r => r.status === 'passed').length ?? 0;
  const failedCount = iteration.criteriaResults?.filter(r => r.status === 'failed').length ?? 0;
  const totalCriteria = iteration.criteriaResults?.length ?? 0;

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <div
        className={cn(
          'rounded-lg border transition-colors',
          iteration.status === 'approved'
            ? 'border-success/30 bg-success/5'
            : iteration.status === 'rejected'
            ? 'border-destructive/50 bg-destructive/5'
            : iteration.status === 'error'
            ? 'border-warning/50 bg-warning/5'
            : 'border-border bg-card'
        )}
      >
        <CollapsibleTrigger asChild>
          <button className="w-full p-3 flex items-start gap-3 hover:bg-accent/50 transition-colors rounded-lg text-left">
            <div className="flex-shrink-0 mt-0.5">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </div>

            <div className="flex-shrink-0 mt-0.5">
              {getStatusIcon(iteration.status)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-sm font-medium">
                  {t('tasks:qa.history.iterationLabel', { number: iteration.iterationNumber })}
                </span>
                {isLatest && (
                  <Badge variant="outline" className="text-xs bg-primary/10 text-primary border-primary/30">
                    {t('tasks:qa.history.latestIteration')}
                  </Badge>
                )}
                <Badge variant={getStatusBadgeVariant(iteration.status)} className="text-xs">
                  {t(`tasks:qa.summary.${iteration.status === 'in_progress' ? 'needsReview' : iteration.status}`)}
                </Badge>
              </div>

              <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatRelativeTime(iteration.completedAt || iteration.startedAt)}
                </span>
                {iteration.issuesFound > 0 && (
                  <span className="flex items-center gap-1 text-destructive">
                    <AlertTriangle className="h-3 w-3" />
                    {t('tasks:qa.issues.issueCount', { count: iteration.issuesFound })}
                  </span>
                )}
                {totalCriteria > 0 && (
                  <span className="flex items-center gap-1">
                    <ListChecks className="h-3 w-3" />
                    {passedCount}/{totalCriteria} {t('tasks:qa.criteria.passed').toLowerCase()}
                  </span>
                )}
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-3 pt-0 space-y-3 border-t border-border/50 mt-2">
            {/* Iteration details */}
            <div className="grid grid-cols-2 gap-2 text-xs pt-3">
              <div>
                <span className="text-muted-foreground">{t('tasks:qa.history.iteration')}:</span>{' '}
                <span className="font-mono">#{iteration.iterationNumber}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:qa.history.result')}:</span>{' '}
                <Badge variant={getStatusBadgeVariant(iteration.status)} className="text-xs ml-1">
                  {t(`tasks:qa.summary.${iteration.status === 'in_progress' ? 'needsReview' : iteration.status}`)}
                </Badge>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:qa.history.timestamp')}:</span>{' '}
                <span>{formatDateTime(iteration.startedAt)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:qa.history.duration')}:</span>{' '}
                <span>{formatDuration(iteration.startedAt, iteration.completedAt)}</span>
              </div>
            </div>

            {/* Criteria summary */}
            {totalCriteria > 0 && (
              <div className="bg-muted/50 rounded p-2 text-xs space-y-1">
                <div className="font-medium text-muted-foreground mb-1 flex items-center gap-1">
                  <FileCheck className="h-3 w-3" />
                  {t('tasks:qa.criteria.title')}
                </div>
                <div className="flex items-center justify-between">
                  <span>{t('tasks:qa.criteria.passed')}:</span>
                  <span className="font-medium text-success">{passedCount}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>{t('tasks:qa.criteria.failed')}:</span>
                  <span className="font-medium text-destructive">{failedCount}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>{t('tasks:qa.criteria.total')}:</span>
                  <span className="font-medium">{totalCriteria}</span>
                </div>
                {totalCriteria > 0 && (
                  <div className="flex items-center justify-between pt-1 border-t border-border/50">
                    <span>{t('tasks:qa.criteria.passRate')}:</span>
                    <span className={cn(
                      "font-medium",
                      passedCount === totalCriteria ? "text-success" :
                      passedCount > 0 ? "text-warning" : "text-destructive"
                    )}>
                      {Math.round((passedCount / totalCriteria) * 100)}%
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Issues summary */}
            {iteration.issuesSummary && (
              <div className="bg-destructive/10 border border-destructive/30 rounded p-2 text-xs">
                <div className="font-medium text-destructive mb-1 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  {t('tasks:qa.issues.title')}
                </div>
                <div className="text-muted-foreground whitespace-pre-wrap">
                  {iteration.issuesSummary}
                </div>
              </div>
            )}

            {/* Fix request indicator */}
            {iteration.fixRequestPath && (
              <div className="bg-warning/10 border border-warning/30 rounded p-2 text-xs">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-3 w-3 text-warning" />
                  <span className="text-muted-foreground">
                    Fix request generated: <span className="font-mono">{iteration.fixRequestPath}</span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
