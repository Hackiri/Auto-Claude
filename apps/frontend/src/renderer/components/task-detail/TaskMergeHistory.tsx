import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  GitMerge,
  Loader2,
  AlertCircle,
  FileText,
  FilePlus,
  FileX,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  RotateCcw
} from 'lucide-react';
import { ScrollArea } from '../ui/scroll-area';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { cn } from '../../lib/utils';
import { useProjectStore } from '../../stores/project-store';
import type { Task, MergeHistoryEntry, } from '../../../shared/types';

interface TaskMergeHistoryProps {
  task: Task;
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

// Format duration in seconds to readable string
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

export function TaskMergeHistory({ task }: TaskMergeHistoryProps) {
  const { t } = useTranslation(['tasks']);
  const selectedProject = useProjectStore((state) => state.getSelectedProject());

  // State for merge history listing
  const [mergeHistory, setMergeHistory] = useState<MergeHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // State for expanded merge entries
  const [expandedMerges, setExpandedMerges] = useState<Set<string>>(new Set());

  // State for rollback functionality
  const [showRollbackDialog, setShowRollbackDialog] = useState(false);
  const [rollbackMergeId, setRollbackMergeId] = useState<string | null>(null);
  const [isRollingBack, setIsRollingBack] = useState(false);
  const [rollbackError, setRollbackError] = useState<string | null>(null);
  const [rollbackSuccess, setRollbackSuccess] = useState<string | null>(null);

  // Load merge history from backend
  const loadMergeHistory = useCallback(async () => {
    if (!selectedProject) return;

    setIsLoading(true);
    setError(null);

    try {
      // Check if the electronAPI method exists (it may not be implemented yet)
      if (!window.electronAPI.getMergeHistory) {
        throw new Error('Merge history API not yet implemented');
      }

      const result = await window.electronAPI.getMergeHistory(selectedProject.id);
      if (!result.success || !result.data) {
        throw new Error(result.error || 'Failed to load merge history');
      }

      // Filter merges for this task
      const taskMerges = result.data.filter(
        (merge: MergeHistoryEntry) => merge.task_id === task.id || merge.spec_name === task.specId
      );

      // Sort by started_at descending (most recent first)
      taskMerges.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());

      setMergeHistory(taskMerges);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [selectedProject, task.id, task.specId]);

  // Load merge history on mount
  useEffect(() => {
    loadMergeHistory();
  }, [loadMergeHistory]);

  // Toggle merge expansion
  const toggleMerge = useCallback((mergeId: string) => {
    setExpandedMerges(prev => {
      const next = new Set(prev);
      if (next.has(mergeId)) {
        next.delete(mergeId);
      } else {
        next.add(mergeId);
      }
      return next;
    });
  }, []);

  // Show rollback confirmation dialog
  const handleShowRollbackDialog = useCallback((mergeId: string) => {
    setRollbackMergeId(mergeId);
    setRollbackError(null);
    setShowRollbackDialog(true);
  }, []);

  // Execute rollback
  const handleRollback = useCallback(async () => {
    if (!rollbackMergeId || !selectedProject) return;

    setIsRollingBack(true);
    setRollbackError(null);
    setRollbackSuccess(null);

    try {
      // Check if the electronAPI method exists
      if (!window.electronAPI.rollbackMerge) {
        throw new Error('Rollback API not yet implemented');
      }

      const result = await window.electronAPI.rollbackMerge(
        selectedProject.id,
        rollbackMergeId
      );

      if (!result.success) {
        throw new Error(result.error || 'Failed to rollback merge');
      }

      // Success - show message and reload history
      setRollbackSuccess('Merge rolled back successfully');
      setShowRollbackDialog(false);
      setRollbackMergeId(null);

      // Reload merge history to reflect changes
      await loadMergeHistory();

      // Clear success message after 3 seconds
      setTimeout(() => setRollbackSuccess(null), 3000);
    } catch (err) {
      setRollbackError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsRollingBack(false);
    }
  }, [rollbackMergeId, selectedProject, loadMergeHistory]);

  // Render loading state
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center py-12">
          <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-muted-foreground" />
          <p className="text-sm font-medium text-muted-foreground">
            {t('tasks:mergeHistory.loading')}
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
            {t('tasks:mergeHistory.errorLoading')}
          </p>
          <p className="text-xs text-muted-foreground mb-4">{error}</p>
          <Button onClick={loadMergeHistory} size="sm" variant="outline">
            {t('tasks:mergeHistory.retry')}
          </Button>
        </div>
      </div>
    );
  }

  // Render empty state
  if (mergeHistory.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center py-12">
          <GitMerge className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm font-medium text-muted-foreground mb-1">
            {t('tasks:mergeHistory.noHistory')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('tasks:mergeHistory.noHistoryDescription')}
          </p>
        </div>
      </div>
    );
  }

  // Render merge history list
  return (
    <>
      <ScrollArea className="h-full">
        <div className="p-4 space-y-2">
          {/* Success message */}
          {rollbackSuccess && (
            <div className="bg-success/10 border border-success/30 rounded-lg p-3 mb-2">
              <div className="flex items-center gap-2 text-success">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-sm font-medium">{rollbackSuccess}</span>
              </div>
            </div>
          )}

          {mergeHistory.map((merge) => (
            <MergeEntryItem
              key={merge.merge_id}
              merge={merge}
              isExpanded={expandedMerges.has(merge.merge_id)}
              onToggle={() => toggleMerge(merge.merge_id)}
              onRollback={() => handleShowRollbackDialog(merge.merge_id)}
            />
          ))}
        </div>
      </ScrollArea>

      {/* Rollback Confirmation Dialog */}
      <AlertDialog open={showRollbackDialog} onOpenChange={setShowRollbackDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-warning" />
              Rollback Merge
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="text-sm text-muted-foreground space-y-3">
                <p>
                  Are you sure you want to rollback this merge?
                </p>
                <p className="text-warning">
                  This will revert all changes from this merge. The merge history entry will remain for audit purposes.
                </p>
                {rollbackError && (
                  <p className="text-destructive bg-destructive/10 px-3 py-2 rounded-lg text-sm">
                    {rollbackError}
                  </p>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRollingBack}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleRollback();
              }}
              disabled={isRollingBack}
              className="bg-warning text-warning-foreground hover:bg-warning/90"
            >
              {isRollingBack ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rolling Back...
                </>
              ) : (
                <>
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Rollback Merge
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

// Individual merge entry component
interface MergeEntryItemProps {
  merge: MergeHistoryEntry;
  isExpanded: boolean;
  onToggle: () => void;
  onRollback: () => void;
}

function MergeEntryItem({ merge, isExpanded, onToggle, onRollback }: MergeEntryItemProps) {
  const { t } = useTranslation(['tasks']);
  const totalFiles = merge.files_changed.length + merge.files_added.length + merge.files_deleted.length;

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <div
        className={cn(
          'rounded-lg border transition-colors',
          merge.success ? 'border-border bg-card' : 'border-destructive/50 bg-destructive/5'
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
              {merge.success ? (
                <CheckCircle2 className="h-5 w-5 text-success" />
              ) : (
                <XCircle className="h-5 w-5 text-destructive" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-sm font-medium">
                  {t('tasks:mergeHistory.mergedTo', { branch: merge.target_branch })}
                </span>
                <Badge variant="outline" className="text-xs">
                  <Clock className="h-3 w-3 mr-1" />
                  {formatRelativeTime(merge.completed_at || merge.started_at)}
                </Badge>
              </div>

              <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                <span>{t('tasks:mergeHistory.filesChanged', { count: totalFiles })}</span>
                {merge.total_conflicts > 0 && (
                  <span className="flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {t('tasks:mergeHistory.conflicts', { count: merge.total_conflicts })}
                  </span>
                )}
                <span>{formatDuration(merge.duration_seconds)}</span>
              </div>
            </div>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="px-3 pb-3 pt-0 space-y-3 border-t border-border/50 mt-2">
            {/* Merge details */}
            <div className="grid grid-cols-2 gap-2 text-xs pt-3">
              <div>
                <span className="text-muted-foreground">{t('tasks:mergeHistory.source')}:</span>{' '}
                <span className="font-mono">{merge.source_branch}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:mergeHistory.target')}:</span>{' '}
                <span className="font-mono">{merge.target_branch}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:mergeHistory.started')}:</span>{' '}
                <span>{formatDateTime(merge.started_at)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t('tasks:mergeHistory.completed')}:</span>{' '}
                <span>{merge.completed_at ? formatDateTime(merge.completed_at) : t('tasks:mergeHistory.notAvailable')}</span>
              </div>
            </div>

            {/* Conflict resolution stats */}
            {merge.total_conflicts > 0 && (
              <div className="bg-muted/50 rounded p-2 text-xs space-y-1">
                <div className="font-medium text-muted-foreground mb-1">{t('tasks:mergeHistory.conflictResolution')}</div>
                <div className="flex items-center justify-between">
                  <span>{t('tasks:mergeHistory.autoResolved')}:</span>
                  <span className="font-medium">{merge.auto_resolved_count}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>{t('tasks:mergeHistory.aiResolved')}:</span>
                  <span className="font-medium">{merge.ai_resolved_count}</span>
                </div>
                {merge.ai_tokens_used > 0 && (
                  <div className="flex items-center justify-between">
                    <span>{t('tasks:mergeHistory.aiTokensUsed')}:</span>
                    <span className="font-medium">{merge.ai_tokens_used.toLocaleString()}</span>
                  </div>
                )}
              </div>
            )}

            {/* Files changed */}
            {totalFiles > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-muted-foreground">{t('tasks:mergeHistory.filesChangedLabel')}</div>
                <div className="space-y-1">
                  {merge.files_added.map((file, idx) => (
                    <div key={`added-${idx}`} className="flex items-center gap-2 text-xs">
                      <FilePlus className="h-3 w-3 text-success flex-shrink-0" />
                      <span className="font-mono text-success truncate">{file}</span>
                    </div>
                  ))}
                  {merge.files_changed.map((file, idx) => (
                    <div key={`changed-${idx}`} className="flex items-center gap-2 text-xs">
                      <FileText className="h-3 w-3 text-info flex-shrink-0" />
                      <span className="font-mono truncate">{file}</span>
                    </div>
                  ))}
                  {merge.files_deleted.map((file, idx) => (
                    <div key={`deleted-${idx}`} className="flex items-center gap-2 text-xs">
                      <FileX className="h-3 w-3 text-destructive flex-shrink-0" />
                      <span className="font-mono text-destructive truncate">{file}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error message if merge failed */}
            {!merge.success && merge.error_message && (
              <div className="bg-destructive/10 border border-destructive/30 rounded p-2 text-xs">
                <div className="font-medium text-destructive mb-1">{t('tasks:mergeHistory.error')}</div>
                <div className="text-muted-foreground">{merge.error_message}</div>
              </div>
            )}

            {/* Rollback button - only show for successful merges */}
            {merge.success && (
              <div className="pt-2 border-t border-border/50">
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-muted-foreground hover:text-warning hover:bg-warning/10"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRollback();
                  }}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  {t('tasks:mergeHistory.rollback')}
                </Button>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
