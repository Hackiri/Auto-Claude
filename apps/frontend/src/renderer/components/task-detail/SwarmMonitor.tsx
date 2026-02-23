import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/utils';
import type { SwarmState } from '../../../shared/types';

interface SwarmMonitorProps {
  swarmState: SwarmState;
}

const statusColors: Record<string, string> = {
  idle: 'bg-muted text-muted-foreground',
  claiming: 'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400',
  working: 'bg-blue-500/20 text-blue-600 dark:text-blue-400',
  done: 'bg-green-500/20 text-green-600 dark:text-green-400',
  error: 'bg-destructive/20 text-destructive',
};

const taskStatusColors: Record<string, string> = {
  pending: 'bg-muted',
  in_progress: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-destructive',
};

export function SwarmMonitor({ swarmState }: SwarmMonitorProps) {
  const { t } = useTranslation(['tasks']);
  const activeWorkers = swarmState.workers.filter(w => w.status === 'working').length;
  const taskEntries = Object.entries(swarmState.tasks);

  if (swarmState.workers.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 p-3 rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">{t('tasks:swarmMode.monitor')}</h4>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{swarmState.completed_tasks}/{swarmState.total_tasks} {t('tasks:detail.subtasksCompleted', { defaultValue: 'completed' })}</span>
          <span>{t('tasks:swarmMode.workersActive', { count: activeWorkers })}</span>
        </div>
      </div>

      {/* Worker Status Cards */}
      <div className="grid grid-cols-3 gap-2">
        {swarmState.workers.map((worker) => (
          <div
            key={worker.id}
            className={cn(
              'rounded-md p-2 text-xs',
              statusColors[worker.status] || 'bg-muted'
            )}
          >
            <div className="font-medium">{worker.id}</div>
            <div className="capitalize">{worker.status}</div>
            {worker.current_task && (
              <div className="truncate text-[10px] opacity-75 mt-0.5">{worker.current_task}</div>
            )}
            <div className="text-[10px] opacity-60 mt-0.5">{worker.tasks_completed} {t('tasks:swarmMode.done')}</div>
          </div>
        ))}
      </div>

      {/* Task Progress Grid */}
      {taskEntries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {taskEntries.map(([taskId, task]) => (
            <div
              key={taskId}
              className={cn(
                'h-3 w-3 rounded-sm',
                taskStatusColors[task.status] || 'bg-muted'
              )}
              title={`${taskId}: ${task.status}${task.assigned_to ? ` (${task.assigned_to})` : ''}`}
            />
          ))}
        </div>
      )}

      {/* Progress Bar */}
      {swarmState.total_tasks > 0 && (
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-green-500 transition-all duration-300"
            style={{ width: `${(swarmState.completed_tasks / swarmState.total_tasks) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
