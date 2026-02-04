import { useTranslation } from 'react-i18next';
import { Play, Pause, CheckCircle2, XCircle, Clock, Archive, Loader2 } from 'lucide-react';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';
import { cn } from '../../../lib/utils';
import type { AgentSession } from '../../../../shared/types';

interface SessionHeaderProps {
  session: AgentSession;
  taskStats: {
    pending: number;
    inProgress: number;
    completed: number;
    failed: number;
    total: number;
    completedPercentage: number;
  };
}

export function SessionHeader({ session, taskStats }: SessionHeaderProps) {
  const { t } = useTranslation('agentSessions');
  const statusConfig = getStatusConfig(session.status, t);

  return (
    <div className="border-b border-border px-6 py-5 bg-card/30">
      {/* Title and status row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold truncate">{session.title}</h2>
            <Badge
              variant="outline"
              className={cn('text-xs px-2 py-0.5', statusConfig.className)}
            >
              {session.status === 'running' ? (
                <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
              ) : (
                <statusConfig.icon className="h-3 w-3 mr-1.5" />
              )}
              {statusConfig.label}
            </Badge>
          </div>

          <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground/70">{t('detail.phase')}:</span>
              <span className="text-foreground font-medium capitalize">
                {t(`phases.${session.currentPhase}`)}
              </span>
            </div>
            {session.startedAt && (
              <div className="flex items-center gap-1.5">
                <span className="text-muted-foreground/70">{t('detail.startedAt')}:</span>
                <span className="text-foreground">{formatTime(session.startedAt)}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Progress section */}
      <div className="mt-5 p-4 rounded-lg bg-muted/30 border border-border/50">
        <div className="flex items-center justify-between text-sm mb-3">
          <span className="text-muted-foreground font-medium">{t('detail.progress')}</span>
          <span className="font-semibold">
            {taskStats.completed}/{taskStats.total} tasks
            <span className="text-muted-foreground font-normal ml-1.5">({session.overallProgress}%)</span>
          </span>
        </div>
        <Progress value={session.overallProgress} className="h-2.5" />

        {/* Task breakdown */}
        <div className="flex items-center gap-6 mt-4">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/30" />
            <span className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{taskStats.pending}</span> {t('kanban.pending')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
            <span className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{taskStats.inProgress}</span> {t('kanban.inProgress')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
            <span className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{taskStats.completed}</span> {t('kanban.completed')}
            </span>
          </div>
          {taskStats.failed > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
              <span className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{taskStats.failed}</span> Failed
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getStatusConfig(status: AgentSession['status'], t: (key: string) => string) {
  switch (status) {
    case 'running':
      return {
        icon: Play,
        label: t('status.running'),
        className: 'text-green-600 border-green-600/30 bg-green-500/10'
      };
    case 'paused':
      return {
        icon: Pause,
        label: t('status.paused'),
        className: 'text-yellow-600 border-yellow-600/30 bg-yellow-500/10'
      };
    case 'completed':
      return {
        icon: CheckCircle2,
        label: t('status.completed'),
        className: 'text-blue-600 border-blue-600/30 bg-blue-500/10'
      };
    case 'failed':
      return {
        icon: XCircle,
        label: t('status.failed'),
        className: 'text-red-600 border-red-600/30 bg-red-500/10'
      };
    case 'archived':
      return {
        icon: Archive,
        label: t('status.archived'),
        className: 'text-muted-foreground border-muted-foreground/30 bg-muted'
      };
    default:
      return {
        icon: Clock,
        label: t('status.pending'),
        className: 'text-muted-foreground border-muted-foreground/30'
      };
  }
}

function formatTime(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).format(new Date(date));
}
