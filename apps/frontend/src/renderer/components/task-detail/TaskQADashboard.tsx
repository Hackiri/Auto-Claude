import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ClipboardCheck,
  History,
  TrendingUp,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  RefreshCw
} from 'lucide-react';
import { ScrollArea } from '../ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { QACriteriaList } from './QACriteriaList';
import { QAIterationHistory } from './QAIterationHistory';
import { QATrendChart } from './QATrendChart';
import { cn } from '../../lib/utils';
import type {
  QACriterionResult,
  QAIterationRecord,
  QATrendData,
  QAValidationSummary
} from '../../../shared/types';

interface TaskQADashboardProps {
  criteria: QACriterionResult[];
  iterations: QAIterationRecord[];
  trendData: QATrendData | null;
  summary?: QAValidationSummary | null;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onRefresh?: () => void;
  className?: string;
}

type QADashboardTab = 'criteria' | 'history' | 'trends';

/**
 * Main QA Dashboard component that composes QACriteriaList, QAIterationHistory, and QATrendChart
 * Displays validation results with tabs for different views
 */
export function TaskQADashboard({
  criteria,
  iterations,
  trendData,
  summary,
  isLoading = false,
  error = null,
  onRetry,
  onRefresh,
  className
}: TaskQADashboardProps) {
  const { t } = useTranslation(['tasks']);
  const [activeTab, setActiveTab] = useState<QADashboardTab>('criteria');

  // Calculate summary stats if not provided
  const passedCount = summary?.passedCriteria ?? criteria.filter(c => c.status === 'passed').length;
  const failedCount = summary?.failedCriteria ?? criteria.filter(c => c.status === 'failed').length;
  const totalCount = summary?.totalCriteria ?? criteria.length;
  const passRate = totalCount > 0 ? Math.round((passedCount / totalCount) * 100) : 0;
  const lastIterationStatus = summary?.lastIterationStatus ??
    (iterations.length > 0 ? iterations[iterations.length - 1]?.status : undefined);

  // Determine if we have any QA data
  const hasData = criteria.length > 0 || iterations.length > 0 || trendData !== null;

  // Loading state
  if (isLoading) {
    return (
      <div className={cn('h-full flex items-center justify-center', className)}>
        <div className="text-center py-12">
          <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-muted-foreground" />
          <p className="text-sm font-medium text-muted-foreground">
            {t('tasks:qa.dashboard.loading')}
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={cn('h-full flex items-center justify-center', className)}>
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

  // Empty state - no QA data yet
  if (!hasData) {
    return (
      <div className={cn('h-full flex items-center justify-center', className)}>
        <div className="text-center py-12">
          <ClipboardCheck className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm font-medium text-muted-foreground mb-1">
            {t('tasks:qa.dashboard.noData')}
          </p>
          <p className="text-xs text-muted-foreground/70">
            {t('tasks:qa.dashboard.noDataDescription')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('h-full flex flex-col', className)}>
      {/* Header with summary */}
      <div className="flex-shrink-0 px-4 pt-4 pb-3 border-b border-border/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-medium text-foreground">
              {t('tasks:qa.dashboard.title')}
            </h2>
          </div>
          {onRefresh && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onRefresh}
              className="h-7 px-2"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {/* Summary badges */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Overall status */}
          {lastIterationStatus && (
            <Badge
              variant={lastIterationStatus === 'approved' ? 'default' :
                       lastIterationStatus === 'rejected' ? 'destructive' : 'secondary'}
              className="text-xs flex items-center gap-1"
            >
              {lastIterationStatus === 'approved' && <CheckCircle2 className="h-3 w-3" />}
              {lastIterationStatus === 'rejected' && <XCircle className="h-3 w-3" />}
              {lastIterationStatus === 'in_progress' && <Loader2 className="h-3 w-3 animate-spin" />}
              {t(`tasks:qa.summary.${lastIterationStatus === 'in_progress' ? 'needsReview' : lastIterationStatus}`)}
            </Badge>
          )}

          {/* Pass rate */}
          {totalCount > 0 && (
            <Badge
              variant="outline"
              className={cn(
                'text-xs tabular-nums',
                passRate >= 80 ? 'text-success border-success/30 bg-success/10' :
                passRate >= 60 ? 'text-warning border-warning/30 bg-warning/10' :
                'text-destructive border-destructive/30 bg-destructive/10'
              )}
            >
              {passRate}% {t('tasks:qa.criteria.passRate')}
            </Badge>
          )}

          {/* Criteria counts */}
          {totalCount > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="text-success">{passedCount} {t('tasks:qa.criteria.passed').toLowerCase()}</span>
              <span>·</span>
              <span className="text-destructive">{failedCount} {t('tasks:qa.criteria.failed').toLowerCase()}</span>
              <span>·</span>
              <span>{totalCount} {t('tasks:qa.criteria.total').toLowerCase()}</span>
            </div>
          )}

          {/* Iteration count */}
          {iterations.length > 0 && (
            <Badge variant="outline" className="text-xs">
              {iterations.length} {iterations.length === 1 ? 'iteration' : 'iterations'}
            </Badge>
          )}
        </div>
      </div>

      {/* Tabs navigation */}
      <div className="flex-shrink-0 px-4 pt-3">
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as QADashboardTab)}>
          <TabsList className="w-full">
            <TabsTrigger value="criteria" className="flex-1 text-xs gap-1.5">
              <ClipboardCheck className="h-3.5 w-3.5" />
              {t('tasks:qa.criteria.title')}
              {criteria.length > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-muted">
                  {criteria.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="history" className="flex-1 text-xs gap-1.5">
              <History className="h-3.5 w-3.5" />
              {t('tasks:qa.history.title')}
              {iterations.length > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-muted">
                  {iterations.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="trends" className="flex-1 text-xs gap-1.5">
              <TrendingUp className="h-3.5 w-3.5" />
              {t('tasks:qa.trends.title')}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Tab content with scroll area */}
      <div className="flex-1 min-h-0">
        <ScrollArea className="h-full">
          {activeTab === 'criteria' && (
            <QACriteriaList criteria={criteria} />
          )}
          {activeTab === 'history' && (
            <QAIterationHistory
              iterations={iterations}
              isLoading={false}
              error={null}
              onRetry={onRetry}
            />
          )}
          {activeTab === 'trends' && (
            <QATrendChart trendData={trendData} />
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
