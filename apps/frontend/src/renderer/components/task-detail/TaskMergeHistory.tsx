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
  ChevronRight
} from 'lucide-react';
import { ScrollArea } from '../ui/scroll-area';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { cn } from '../../lib/utils';
import { useProjectStore } from '../../stores/project-store';
import type { Task } from '../../../shared/types';

interface TaskMergeHistoryProps {
  task: Task;
}

/**
 * Merge history entry structure (matches backend MergeHistoryEntry)
 */
interface MergeHistoryEntry {
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
interface MergeConflictRecord {
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
    <ScrollArea className="h-full">
      <div className="p-4 space-y-2">
        {mergeHistory.map((merge) => (
          <MergeEntryItem
            key={merge.merge_id}
            merge={merge}
            isExpanded={expandedMerges.has(merge.merge_id)}
            onToggle={() => toggleMerge(merge.merge_id)}
          />
        ))}
      </div>
    </ScrollArea>
  );
}

// Individual merge entry component
interface MergeEntryItemProps {
  merge: MergeHistoryEntry;
  isExpanded: boolean;
  onToggle: () => void;
}

function MergeEntryItem({ merge, isExpanded, onToggle }: MergeEntryItemProps) {
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
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
