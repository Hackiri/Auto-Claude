import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock, Play, CheckCircle2 } from 'lucide-react';
import { ScrollArea } from '../../ui/scroll-area';
import { TaskCard } from './TaskCard';
import { cn } from '../../../lib/utils';
import type { SessionTask } from '../../../../shared/types';

interface SessionKanbanProps {
  sessionId: string;
  tasks: SessionTask[];
}

export function SessionKanban({ sessionId, tasks }: SessionKanbanProps) {
  const { t } = useTranslation('agentSessions');

  // Group tasks by status
  const columns = useMemo(() => {
    const pending: SessionTask[] = [];
    const inProgress: SessionTask[] = [];
    const completed: SessionTask[] = [];

    for (const task of tasks) {
      switch (task.status) {
        case 'pending':
          pending.push(task);
          break;
        case 'in_progress':
          inProgress.push(task);
          break;
        case 'completed':
        case 'failed':
          completed.push(task);
          break;
      }
    }

    return { pending, inProgress, completed };
  }, [tasks]);

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-center p-8">
        <div className="text-muted-foreground">
          <p className="text-sm">No tasks in the implementation plan yet</p>
          <p className="text-xs mt-1 text-muted-foreground/60">Tasks will appear here once planning completes</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex gap-4 p-4 overflow-x-auto bg-muted/20">
      <KanbanColumn
        title={t('kanban.pending')}
        count={columns.pending.length}
        icon={Clock}
        colorClass="text-muted-foreground"
        headerBgClass="bg-muted/50"
      >
        {columns.pending.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </KanbanColumn>

      <KanbanColumn
        title={t('kanban.inProgress')}
        count={columns.inProgress.length}
        icon={Play}
        colorClass="text-blue-600 dark:text-blue-400"
        headerBgClass="bg-blue-500/10"
      >
        {columns.inProgress.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </KanbanColumn>

      <KanbanColumn
        title={t('kanban.completed')}
        count={columns.completed.length}
        icon={CheckCircle2}
        colorClass="text-green-600 dark:text-green-400"
        headerBgClass="bg-green-500/10"
      >
        {columns.completed.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}
      </KanbanColumn>
    </div>
  );
}

interface KanbanColumnProps {
  title: string;
  count: number;
  icon: React.ElementType;
  colorClass: string;
  headerBgClass: string;
  children: React.ReactNode;
}

function KanbanColumn({ title, count, icon: Icon, colorClass, headerBgClass, children }: KanbanColumnProps) {
  return (
    <div className="flex-shrink-0 w-80 flex flex-col max-h-full bg-card/50 rounded-lg border border-border/50">
      {/* Column header */}
      <div className={cn('flex items-center gap-2.5 px-4 py-3 rounded-t-lg border-b border-border/50', headerBgClass)}>
        <Icon className={cn('h-4 w-4', colorClass)} />
        <h3 className="font-medium text-sm">{title}</h3>
        <span className={cn('ml-auto text-xs font-medium px-2 py-0.5 rounded-full bg-background/80', colorClass)}>
          {count}
        </span>
      </div>

      {/* Column content */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-3 space-y-2">
          {children}
        </div>
      </ScrollArea>
    </div>
  );
}
