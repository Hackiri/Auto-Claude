/**
 * SubtaskDependencyBadge Component
 * =================================
 *
 * Displays dependency status badges for subtasks:
 * - "Blocked by N" - when subtask has unresolved dependencies
 * - "Blocks N" - when other subtasks are waiting on this one
 *
 * Includes tooltips showing the specific subtask names.
 */

import { Lock, Hourglass } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import type { Subtask, SubtaskDependencyInfo } from '../../../shared/types/task';
import { getSubtaskDisplayName } from '../../hooks/useSubtaskDependencies';

interface SubtaskDependencyBadgeProps {
  dependencyInfo: SubtaskDependencyInfo;
  allSubtasks: Subtask[];
}

/**
 * List of subtask names for tooltip content
 */
function DependencyList({
  subtaskIds,
  allSubtasks,
  label,
}: {
  subtaskIds: string[];
  allSubtasks: Subtask[];
  label: string;
}) {
  if (subtaskIds.length === 0) return null;

  return (
    <div className="space-y-1">
      <div className="font-medium text-xs">{label}</div>
      <ul className="text-xs space-y-0.5 pl-2">
        {subtaskIds.map(id => (
          <li key={id} className="flex items-center gap-1">
            <span className="text-muted-foreground">&bull;</span>
            <span>{getSubtaskDisplayName(allSubtasks, id)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SubtaskDependencyBadge({
  dependencyInfo,
  allSubtasks,
}: SubtaskDependencyBadgeProps) {
  const { t } = useTranslation(['tasks']);
  const { isBlocked, isBlocking, unresolvedDependencies, dependentSubtasks } = dependencyInfo;

  // Don't render anything if no dependencies to show
  if (!isBlocked && !isBlocking) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {isBlocked && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="warning" className="cursor-help text-[10px] py-0 px-1.5">
              <Lock className="mr-1 h-3 w-3" />
              {t('tasks:subtasks.blockedBy', {
                count: unresolvedDependencies.length,
                defaultValue: `Blocked by ${unresolvedDependencies.length}`,
              })}
            </Badge>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs">
            <DependencyList
              subtaskIds={unresolvedDependencies}
              allSubtasks={allSubtasks}
              label={t('tasks:subtasks.waitingFor', { defaultValue: 'Waiting for:' })}
            />
          </TooltipContent>
        </Tooltip>
      )}

      {isBlocking && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="info" className="cursor-help text-[10px] py-0 px-1.5">
              <Hourglass className="mr-1 h-3 w-3" />
              {t('tasks:subtasks.blocks', {
                count: dependentSubtasks.length,
                defaultValue: `Blocks ${dependentSubtasks.length}`,
              })}
            </Badge>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs">
            <DependencyList
              subtaskIds={dependentSubtasks}
              allSubtasks={allSubtasks}
              label={t('tasks:subtasks.blocking', { defaultValue: 'Blocking:' })}
            />
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
