import { useState } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Clock, ChevronDown, ClipboardList, Image as ImageIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../ui/collapsible';
import { cn } from '../../lib/utils';
import type { QACriterionResult, QACriterionStatus } from '../../../shared/types';

interface QACriteriaListProps {
  criteria: QACriterionResult[];
}

function getCriterionStatusIcon(status: QACriterionStatus) {
  switch (status) {
    case 'passed':
      return <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-[var(--error)]" />;
    case 'pending':
      return <Clock className="h-4 w-4 text-[var(--info)] animate-pulse" />;
    case 'skipped':
      return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    default:
      return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
  }
}

function getCriterionStatusBadgeVariant(status: QACriterionStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'passed':
      return 'default';
    case 'failed':
      return 'destructive';
    case 'pending':
      return 'secondary';
    case 'skipped':
      return 'outline';
    default:
      return 'outline';
  }
}

export function QACriteriaList({ criteria }: QACriteriaListProps) {
  const { t } = useTranslation(['tasks']);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const passedCount = criteria.filter(c => c.status === 'passed').length;
  const failedCount = criteria.filter(c => c.status === 'failed').length;
  const passRate = criteria.length > 0 ? Math.round((passedCount / criteria.length) * 100) : 0;

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-3">
        {criteria.length === 0 ? (
          <div className="text-center py-12">
            <ClipboardList className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
            <p className="text-sm font-medium text-muted-foreground mb-1">
              {t('tasks:qa.criteria.noCriteria')}
            </p>
            <p className="text-xs text-muted-foreground/70">
              {t('tasks:qa.dashboard.noDataDescription')}
            </p>
          </div>
        ) : (
          <>
            {/* Summary */}
            <div className="flex items-center justify-between text-xs text-muted-foreground pb-2 border-b border-border/50">
              <div className="flex items-center gap-3">
                <span className="text-[var(--success)]">
                  {passedCount} {t('tasks:qa.criteria.passed')}
                </span>
                <span className="text-[var(--error)]">
                  {failedCount} {t('tasks:qa.criteria.failed')}
                </span>
              </div>
              <span className="tabular-nums">{passRate}% {t('tasks:qa.criteria.passRate')}</span>
            </div>

            {/* Criteria list */}
            {criteria.map((criterion, index) => {
              const isExpanded = expandedItems.has(criterion.id);
              const hasEvidence = criterion.evidence && (
                criterion.evidence.errorMessage ||
                criterion.evidence.screenshotPath ||
                criterion.evidence.screenshotBase64 ||
                criterion.evidence.logOutput
              );

              return (
                <Collapsible
                  key={criterion.id}
                  open={isExpanded}
                  onOpenChange={() => toggleExpanded(criterion.id)}
                >
                  <div
                    className={cn(
                      'rounded-xl border border-border bg-secondary/30 p-3 transition-all duration-200',
                      criterion.status === 'passed' && 'border-[var(--success)]/50 bg-[var(--success-light)]',
                      criterion.status === 'failed' && 'border-[var(--error)]/50 bg-[var(--error-light)]',
                      criterion.status === 'pending' && 'border-[var(--info)]/50 bg-[var(--info-light)]'
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {getCriterionStatusIcon(criterion.status)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            'text-[10px] font-medium px-1.5 py-0.5 rounded-full',
                            criterion.status === 'passed' ? 'bg-success/20 text-success' :
                            criterion.status === 'failed' ? 'bg-destructive/20 text-destructive' :
                            criterion.status === 'pending' ? 'bg-info/20 text-info' :
                            'bg-muted text-muted-foreground'
                          )}>
                            #{index + 1}
                          </span>
                          <Badge variant={getCriterionStatusBadgeVariant(criterion.status)}>
                            {t(`tasks:qa.status.${criterion.status}`)}
                          </Badge>
                        </div>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <p className="mt-2 text-sm text-foreground line-clamp-2 cursor-default">
                              {criterion.criterionText}
                            </p>
                          </TooltipTrigger>
                          {criterion.criterionText && criterion.criterionText.length > 100 && (
                            <TooltipContent side="bottom" className="max-w-sm">
                              <p className="text-xs">{criterion.criterionText}</p>
                            </TooltipContent>
                          )}
                        </Tooltip>

                        {/* Collapsible trigger for evidence */}
                        {hasEvidence && (
                          <CollapsibleTrigger asChild>
                            <button
                              className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <ChevronDown className={cn(
                                'h-3 w-3 transition-transform duration-200',
                                isExpanded && 'rotate-180'
                              )} />
                              {t('tasks:qa.criteria.details')}
                            </button>
                          </CollapsibleTrigger>
                        )}
                      </div>
                    </div>

                    {/* Collapsible content with evidence details */}
                    <CollapsibleContent>
                      <div className="mt-3 pt-3 border-t border-border/50 space-y-3">
                        {criterion.evidence?.errorMessage && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">
                              {t('tasks:qa.issues.description')}
                            </p>
                            <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-2">
                              <p className="text-xs text-destructive font-mono whitespace-pre-wrap">
                                {criterion.evidence.errorMessage}
                              </p>
                            </div>
                          </div>
                        )}

                        {criterion.evidence?.expectedResult && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">Expected</p>
                            <p className="text-xs text-foreground bg-muted/50 rounded-lg p-2">
                              {criterion.evidence.expectedResult}
                            </p>
                          </div>
                        )}

                        {criterion.evidence?.actualResult && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">Actual</p>
                            <p className="text-xs text-foreground bg-muted/50 rounded-lg p-2">
                              {criterion.evidence.actualResult}
                            </p>
                          </div>
                        )}

                        {criterion.evidence?.command && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">Command</p>
                            <p className="text-xs text-foreground bg-muted/50 rounded-lg p-2 font-mono">
                              {criterion.evidence.command}
                            </p>
                          </div>
                        )}

                        {criterion.evidence?.logOutput && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground">Log Output</p>
                            <pre className="text-xs text-foreground bg-muted/50 rounded-lg p-2 font-mono overflow-x-auto max-h-32 overflow-y-auto">
                              {criterion.evidence.logOutput}
                            </pre>
                          </div>
                        )}

                        {(criterion.evidence?.screenshotBase64 || criterion.evidence?.screenshotPath) && (
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                              <ImageIcon className="h-3 w-3" />
                              Screenshot
                            </p>
                            {criterion.evidence?.screenshotBase64 ? (
                              <img
                                src={`data:image/png;base64,${criterion.evidence.screenshotBase64}`}
                                alt="Failure screenshot"
                                className="rounded-lg border border-border max-w-full max-h-64 object-contain"
                              />
                            ) : criterion.evidence?.screenshotPath && (
                              <div className="bg-muted/50 rounded-lg p-2 text-xs text-muted-foreground font-mono">
                                {criterion.evidence.screenshotPath}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              );
            })}
          </>
        )}
      </div>
    </ScrollArea>
  );
}
