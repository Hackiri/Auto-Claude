import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Play, Pause, CheckCircle2, XCircle, Clock, Archive, Loader2 } from 'lucide-react';
import { useAgentSessionsStore } from '../../../stores/agent-sessions-store';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';
import { cn } from '../../../lib/utils';
import type { AgentSession } from '../../../../shared/types';

interface SessionListItemProps {
  session: AgentSession;
  isFocused?: boolean;
}

export function SessionListItem({ session, isFocused = false }: SessionListItemProps) {
  const { t } = useTranslation('agentSessions');
  const selectedSessionId = useAgentSessionsStore((state) => state.selectedSessionId);
  const selectSession = useAgentSessionsStore((state) => state.selectSession);

  const isSelected = selectedSessionId === session.id;
  const statusConfig = getStatusConfig(session.status, t);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Scroll focused item into view
  useEffect(() => {
    if (isFocused && buttonRef.current) {
      buttonRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [isFocused]);

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={() => selectSession(session.id)}
      className={cn(
        'w-full text-left rounded-lg p-3.5 transition-all duration-150',
        'border border-transparent',
        'hover:bg-accent/60 hover:border-border/50',
        isSelected && 'bg-accent border-border shadow-sm',
        isFocused && !isSelected && 'ring-2 ring-ring ring-offset-1 ring-offset-background'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Status indicator */}
        <div className={cn(
          'mt-0.5 p-1 rounded-md',
          statusConfig.bgClass
        )}>
          {session.status === 'running' ? (
            <Loader2 className={cn('h-3.5 w-3.5 animate-spin', statusConfig.iconClass)} />
          ) : (
            <statusConfig.icon className={cn('h-3.5 w-3.5', statusConfig.iconClass)} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Title */}
          <p className="font-medium text-sm truncate leading-tight">{session.title}</p>

          {/* Phase and status */}
          <div className="flex items-center gap-2 mt-1.5">
            <span className={cn('text-xs font-medium', statusConfig.textClass)}>
              {statusConfig.label}
            </span>
            {session.currentPhase && session.currentPhase !== 'idle' && (
              <>
                <span className="text-muted-foreground/40">•</span>
                <span className="text-xs text-muted-foreground capitalize">
                  {t(`phases.${session.currentPhase}`)}
                </span>
              </>
            )}
          </div>

          {/* Progress bar for active sessions */}
          {(session.status === 'running' || session.status === 'paused') && (
            <div className="mt-2.5">
              <Progress value={session.overallProgress} className="h-1.5" />
              <p className="text-[10px] text-muted-foreground mt-1">
                {session.overallProgress}%
              </p>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

function getStatusConfig(status: AgentSession['status'], t: (key: string) => string) {
  switch (status) {
    case 'running':
      return {
        icon: Play,
        label: t('status.running'),
        iconClass: 'text-green-600 dark:text-green-400',
        textClass: 'text-green-600 dark:text-green-400',
        bgClass: 'bg-green-500/10'
      };
    case 'paused':
      return {
        icon: Pause,
        label: t('status.paused'),
        iconClass: 'text-yellow-600 dark:text-yellow-400',
        textClass: 'text-yellow-600 dark:text-yellow-400',
        bgClass: 'bg-yellow-500/10'
      };
    case 'completed':
      return {
        icon: CheckCircle2,
        label: t('status.completed'),
        iconClass: 'text-blue-600 dark:text-blue-400',
        textClass: 'text-blue-600 dark:text-blue-400',
        bgClass: 'bg-blue-500/10'
      };
    case 'failed':
      return {
        icon: XCircle,
        label: t('status.failed'),
        iconClass: 'text-red-600 dark:text-red-400',
        textClass: 'text-red-600 dark:text-red-400',
        bgClass: 'bg-red-500/10'
      };
    case 'archived':
      return {
        icon: Archive,
        label: t('status.archived'),
        iconClass: 'text-muted-foreground',
        textClass: 'text-muted-foreground',
        bgClass: 'bg-muted'
      };
    case 'pending':
    default:
      return {
        icon: Clock,
        label: t('status.pending'),
        iconClass: 'text-muted-foreground',
        textClass: 'text-muted-foreground',
        bgClass: 'bg-muted/50'
      };
  }
}
