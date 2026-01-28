import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Terminal, Globe, FileText, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Card, CardContent } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../../ui/collapsible';
import { cn } from '../../../lib/utils';
import type { SessionTask } from '../../../../shared/types';

interface TaskCardProps {
  task: SessionTask;
}

export function TaskCard({ task }: TaskCardProps) {
  const { t } = useTranslation('agentSessions');
  const [isExpanded, setIsExpanded] = useState(false);

  const statusConfig = getStatusConfig(task.status);
  const hasDetails = task.verification || task.files_to_create.length > 0 || task.files_to_modify.length > 0;

  return (
    <Card className={cn(
      'transition-all duration-150 border',
      task.status === 'in_progress' && 'border-blue-500/50 bg-blue-500/5 shadow-sm shadow-blue-500/10',
      task.status === 'completed' && 'border-green-500/30 bg-green-500/5',
      task.status === 'failed' && 'border-red-500/30 bg-red-500/5',
      task.status === 'pending' && 'border-border/50 bg-card/50 hover:border-border hover:bg-card'
    )}>
      <CardContent className="p-3">
        {/* Main content */}
        <div className="flex items-start gap-2.5">
          <div className={cn('mt-0.5 p-1 rounded', statusConfig.bgClass)}>
            {task.status === 'in_progress' ? (
              <Loader2 className={cn('h-3 w-3 animate-spin', statusConfig.iconClass)} />
            ) : (
              <statusConfig.icon className={cn('h-3 w-3', statusConfig.iconClass)} />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm leading-snug font-medium">{task.description}</p>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5 bg-muted/50">
                {task.phaseName}
              </Badge>
            </div>
          </div>
        </div>

        {/* Expandable details */}
        {hasDetails && (
          <Collapsible open={isExpanded} onOpenChange={setIsExpanded} className="mt-3">
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-full pt-2 border-t border-border/30"
              >
                {isExpanded ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                <span>Details</span>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2 space-y-2">
              {/* Verification */}
              {task.verification && (
                <div className="flex items-start gap-2 text-xs p-2 rounded bg-muted/30">
                  {task.verification.type === 'command' ? (
                    <Terminal className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                  ) : (
                    <Globe className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                  )}
                  <div className="flex-1 min-w-0">
                    <span className="text-muted-foreground font-medium">
                      {task.verification.type === 'command'
                        ? t('taskCard.verificationCommand')
                        : t('taskCard.verificationBrowser')}
                    </span>
                    {task.verification.run && (
                      <code className="block mt-1 text-[10px] bg-background/80 px-2 py-1 rounded font-mono text-foreground">
                        {task.verification.run}
                      </code>
                    )}
                    {task.verification.scenario && (
                      <span className="block mt-1 text-muted-foreground">
                        {task.verification.scenario}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Files */}
              {(task.files_to_create.length > 0 || task.files_to_modify.length > 0) && (
                <div className="flex items-start gap-2 text-xs p-2 rounded bg-muted/30">
                  <FileText className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                  <div className="flex-1">
                    <span className="text-muted-foreground font-medium">
                      {t('taskCard.files', {
                        count: task.files_to_create.length + task.files_to_modify.length
                      })}
                    </span>
                  </div>
                </div>
              )}
            </CollapsibleContent>
          </Collapsible>
        )}
      </CardContent>
    </Card>
  );
}

function getStatusConfig(status: SessionTask['status']) {
  switch (status) {
    case 'in_progress':
      return {
        icon: Loader2,
        iconClass: 'text-blue-600 dark:text-blue-400',
        bgClass: 'bg-blue-500/10'
      };
    case 'completed':
      return {
        icon: CheckCircle2,
        iconClass: 'text-green-600 dark:text-green-400',
        bgClass: 'bg-green-500/10'
      };
    case 'failed':
      return {
        icon: XCircle,
        iconClass: 'text-red-600 dark:text-red-400',
        bgClass: 'bg-red-500/10'
      };
    case 'pending':
    default:
      return {
        icon: Clock,
        iconClass: 'text-muted-foreground',
        bgClass: 'bg-muted/50'
      };
  }
}
