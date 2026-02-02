import { useTranslation } from 'react-i18next';
import { GitCompareArrows, Clock, Layers, ListChecks, FileText } from 'lucide-react';
import { useSessionProgress } from '../../../hooks/useSessionProgress';
import { cn } from '../../../lib/utils';
import type { AgentSession } from '../../../../shared/types/agent-session';

interface SessionComparisonProps {
  sessionIds: [string, string] | null;
}

export function SessionComparison({ sessionIds }: SessionComparisonProps) {
  const { t } = useTranslation('agentSessions');

  if (!sessionIds || sessionIds.length < 2) {
    return <EmptyComparisonState />;
  }

  return (
    <div className="flex flex-col h-full overflow-auto p-4 gap-4">
      {/* Title */}
      <div className="flex items-center gap-2 mb-2">
        <GitCompareArrows className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-lg font-medium text-foreground">
          {t('comparison.title')}
        </h2>
      </div>

      {/* Side-by-side panels */}
      <div className="grid grid-cols-2 gap-4 flex-1 min-h-0">
        <SessionPanel sessionId={sessionIds[0]} />
        <SessionPanel sessionId={sessionIds[1]} />
      </div>
    </div>
  );
}

function SessionPanel({ sessionId }: { sessionId: string }) {
  const { t } = useTranslation('agentSessions');
  const { session, taskStats } = useSessionProgress(sessionId);

  if (!session) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-center text-muted-foreground">
        {t('detail.noSelection')}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card flex flex-col gap-3 p-4 overflow-auto">
      {/* Session title */}
      <h3 className="text-sm font-semibold text-foreground truncate">
        {session.title}
      </h3>

      {/* Status */}
      <ComparisonRow
        icon={<Layers className="h-4 w-4" />}
        label={t('comparison.status')}
      >
        <StatusBadge status={session.status} />
      </ComparisonRow>

      {/* Duration */}
      <ComparisonRow
        icon={<Clock className="h-4 w-4" />}
        label={t('comparison.duration')}
      >
        <span className="text-sm text-foreground">
          {formatDuration(session)}
        </span>
      </ComparisonRow>

      {/* Phases */}
      <ComparisonRow
        icon={<Layers className="h-4 w-4" />}
        label={t('comparison.phases')}
      >
        <span className="text-sm text-foreground">
          {session.currentPhase
            ? t(`phases.${session.currentPhase}`)
            : '—'}
        </span>
      </ComparisonRow>

      {/* Subtasks */}
      <ComparisonRow
        icon={<ListChecks className="h-4 w-4" />}
        label={t('comparison.subtasks')}
      >
        <div className="text-sm text-foreground space-y-1">
          <div>{taskStats.completed}/{taskStats.total} {t('kanban.completed').toLowerCase()}</div>
          {taskStats.failed > 0 && (
            <div className="text-destructive">{taskStats.failed} failed</div>
          )}
          {/* Progress bar */}
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${taskStats.completedPercentage}%` }}
            />
          </div>
        </div>
      </ComparisonRow>

      {/* Logs summary */}
      <ComparisonRow
        icon={<FileText className="h-4 w-4" />}
        label={t('comparison.logs')}
      >
        <span className="text-sm text-muted-foreground">
          {session.logStreamActive ? t('logs.streaming') : t('logs.noLogs')}
        </span>
      </ComparisonRow>
    </div>
  );
}

function ComparisonRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="pl-5.5">{children}</div>
    </div>
  );
}

const statusColors: Record<string, string> = {
  running: 'bg-blue-500/10 text-blue-500',
  paused: 'bg-yellow-500/10 text-yellow-500',
  completed: 'bg-green-500/10 text-green-500',
  failed: 'bg-red-500/10 text-red-500',
  archived: 'bg-gray-500/10 text-gray-500',
  pending: 'bg-muted text-muted-foreground',
};

function StatusBadge({ status }: { status: AgentSession['status'] }) {
  const { t } = useTranslation('agentSessions');
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        statusColors[status] ?? statusColors.pending
      )}
    >
      {t(`status.${status}`)}
    </span>
  );
}

function formatDuration(session: AgentSession): string {
  const start = session.startedAt ? new Date(session.startedAt).getTime() : null;
  const end = session.completedAt
    ? new Date(session.completedAt).getTime()
    : Date.now();

  if (!start) return '—';

  const diffMs = end - start;
  const mins = Math.floor(diffMs / 60000);
  const secs = Math.floor((diffMs % 60000) / 1000);

  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function EmptyComparisonState() {
  const { t } = useTranslation('agentSessions');
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="rounded-full bg-muted p-4 mb-4">
        <GitCompareArrows className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium text-foreground mb-2">
        {t('comparison.title')}
      </h3>
      <p className="text-sm text-muted-foreground max-w-md">
        {t('comparison.selectTwo')}
      </p>
    </div>
  );
}
