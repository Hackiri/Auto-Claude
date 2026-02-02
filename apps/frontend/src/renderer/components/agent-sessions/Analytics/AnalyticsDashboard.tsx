import { useTranslation } from 'react-i18next';
import { BarChart3, TrendingUp, PieChart, Layers } from 'lucide-react';
import { useSessionAnalytics } from '../../../hooks/useSessionAnalytics';
import { cn } from '../../../lib/utils';

interface ChartPanelProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function ChartPanel({ title, description, icon, children }: ChartPanelProps) {
  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4 min-h-0">
      <div className="flex items-center gap-2 mb-3">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <h3 className="text-sm font-medium text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}

function MetricsSummary() {
  const { t } = useTranslation('agentSessions');
  const { metrics, sessionCount } = useSessionAnalytics();

  if (!metrics || sessionCount === 0) return null;

  const avgMinutes = Math.floor(metrics.averageDurationMs / 60000);
  const avgSeconds = Math.floor((metrics.averageDurationMs % 60000) / 1000);
  const successPct = Math.round(metrics.successRate * 100);

  return (
    <div className="grid grid-cols-4 gap-3 mb-4">
      <div className="rounded-lg border border-border bg-card p-3 text-center">
        <p className="text-xs text-muted-foreground">{t('analytics.totalSessions')}</p>
        <p className="text-xl font-semibold text-foreground">{metrics.totalSessions}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-3 text-center">
        <p className="text-xs text-muted-foreground">{t('analytics.avgDuration')}</p>
        <p className="text-xl font-semibold text-foreground">
          {avgMinutes > 0
            ? `${avgMinutes}${t('analytics.minutes')}`
            : `${avgSeconds}${t('analytics.seconds')}`}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-3 text-center">
        <p className="text-xs text-muted-foreground">{t('analytics.completed')}</p>
        <p className="text-xl font-semibold text-green-500">{metrics.successCount}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-3 text-center">
        <p className="text-xs text-muted-foreground">{t('analytics.failed')}</p>
        <p className="text-xl font-semibold text-red-500">{metrics.failureCount}</p>
      </div>
    </div>
  );
}

function EmptyAnalyticsState() {
  const { t } = useTranslation('agentSessions');

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="rounded-full bg-muted p-4 mb-4">
        <BarChart3 className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium text-foreground mb-2">
        {t('analytics.noData')}
      </h3>
      <p className="text-sm text-muted-foreground max-w-md">
        {t('analytics.noDataHint')}
      </p>
    </div>
  );
}

function ChartPlaceholder() {
  return (
    <div className="flex items-center justify-center h-full min-h-[180px] text-muted-foreground text-sm">
      {/* Placeholder for chart component - will be replaced by subtask-4-2 and subtask-4-3 */}
    </div>
  );
}

export function AnalyticsDashboard() {
  const { t } = useTranslation('agentSessions');
  const { hasData } = useSessionAnalytics();

  if (!hasData) {
    return <EmptyAnalyticsState />;
  }

  return (
    <div className="flex flex-col h-full p-4 overflow-auto">
      <MetricsSummary />

      <div className={cn(
        'grid gap-4 flex-1 min-h-0',
        'grid-cols-1 md:grid-cols-2',
        'auto-rows-[minmax(250px,1fr)]'
      )}>
        <ChartPanel
          title={t('analytics.executionTime')}
          description={t('analytics.executionTimeDesc')}
          icon={<BarChart3 className="h-4 w-4" />}
        >
          <ChartPlaceholder />
        </ChartPanel>

        <ChartPanel
          title={t('analytics.successRate')}
          description={t('analytics.successRateDesc')}
          icon={<PieChart className="h-4 w-4" />}
        >
          <ChartPlaceholder />
        </ChartPanel>

        <ChartPanel
          title={t('analytics.phaseDuration')}
          description={t('analytics.phaseDurationDesc')}
          icon={<Layers className="h-4 w-4" />}
        >
          <ChartPlaceholder />
        </ChartPanel>

        <ChartPanel
          title={t('analytics.trends')}
          description={t('analytics.trendsDesc')}
          icon={<TrendingUp className="h-4 w-4" />}
        >
          <ChartPlaceholder />
        </ChartPanel>
      </div>
    </div>
  );
}
