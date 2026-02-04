/**
 * useSubtaskDependencies Hook
 * ============================
 *
 * Computes dependency metadata for subtasks, including:
 * - Whether a subtask is blocked (has unresolved dependencies)
 * - Whether a subtask is blocking others
 * - Which specific subtasks are dependencies/dependents
 * - Wave number for understanding execution order
 */

import { useMemo } from 'react';

import type { Subtask, PlanSubtask, SubtaskDependencyInfo, SubtaskStatus } from '../../shared/types/task';

type SubtaskLike = Subtask | PlanSubtask;

/**
 * Compute the wave number for a subtask based on its dependencies.
 *
 * Wave 0: Subtasks with no dependencies
 * Wave N: Subtasks that depend on subtasks in waves < N
 */
function computeWaves(subtasks: SubtaskLike[]): Map<string, number> {
  const waveMap = new Map<string, number>();
  const subtaskIds = new Set(subtasks.map(st => st.id));

  // Build dependency graph (only within this set of subtasks)
  const deps = new Map<string, Set<string>>();
  for (const subtask of subtasks) {
    const blocks = subtask.blocks ?? [];
    // Filter to only dependencies within this subtask set
    const validDeps = blocks.filter((id: string) => subtaskIds.has(id));
    deps.set(subtask.id, new Set(validDeps));
  }

  // Iteratively assign waves
  const remaining = new Set(subtaskIds);
  let currentWave = 0;

  while (remaining.size > 0) {
    const readyThisWave: string[] = [];

    for (const id of remaining) {
      const subtaskDeps = deps.get(id) ?? new Set();
      // Check if all dependencies are already assigned a wave
      const allDepsResolved = [...subtaskDeps].every(
        depId => !remaining.has(depId) || waveMap.has(depId),
      );
      if (allDepsResolved) {
        readyThisWave.push(id);
      }
    }

    if (readyThisWave.length === 0 && remaining.size > 0) {
      // Circular dependency detected - assign remaining to current wave
      for (const id of remaining) {
        waveMap.set(id, currentWave);
      }
      break;
    }

    for (const id of readyThisWave) {
      waveMap.set(id, currentWave);
      remaining.delete(id);
    }

    currentWave++;
  }

  return waveMap;
}

/**
 * Hook to compute dependency metadata for a list of subtasks.
 *
 * @param subtasks - Array of subtasks (either Subtask or PlanSubtask)
 * @returns Map from subtask ID to SubtaskDependencyInfo
 */
export function useSubtaskDependencies(
  subtasks: SubtaskLike[],
): Map<string, SubtaskDependencyInfo> {
  return useMemo(() => {
    const completedStatuses: SubtaskStatus[] = ['completed'];
    const completedIds = new Set(
      subtasks.filter(st => completedStatuses.includes(st.status)).map(st => st.id),
    );
    const subtaskIds = new Set(subtasks.map(st => st.id));

    // Compute wave numbers
    const waveMap = computeWaves(subtasks);

    // Build the metadata map
    const metadata = new Map<string, SubtaskDependencyInfo>();

    for (const subtask of subtasks) {
      const blocks = subtask.blocks ?? [];
      const blockedBy = subtask.blockedBy ?? [];

      // Filter to only dependencies within this subtask set
      const validBlocks = blocks.filter((id: string) => subtaskIds.has(id));
      const validBlockedBy = blockedBy.filter((id: string) => subtaskIds.has(id));

      // Find unresolved dependencies (not yet completed)
      const unresolvedDependencies = validBlocks.filter((depId: string) => !completedIds.has(depId));

      // Find subtasks that are waiting on this one (not yet completed dependents)
      const dependentSubtasks = validBlockedBy.filter((depId: string) => !completedIds.has(depId));

      const info: SubtaskDependencyInfo = {
        subtaskId: subtask.id,
        isBlocked: unresolvedDependencies.length > 0,
        isBlocking: dependentSubtasks.length > 0,
        unresolvedDependencies,
        dependentSubtasks,
        wave: waveMap.get(subtask.id) ?? 0,
      };

      metadata.set(subtask.id, info);
    }

    return metadata;
  }, [subtasks]);
}

/**
 * Get the title/description for a subtask by ID.
 * Useful for displaying dependency names in tooltips.
 */
export function getSubtaskDisplayName(subtasks: SubtaskLike[], id: string): string {
  const subtask = subtasks.find(st => st.id === id);
  if (!subtask) return id;

  // PlanSubtask has description, Subtask has title
  if ('title' in subtask && subtask.title) {
    return subtask.title;
  }
  if ('description' in subtask && subtask.description) {
    // Truncate long descriptions
    const desc = subtask.description;
    return desc.length > 40 ? `${desc.slice(0, 37)}...` : desc;
  }
  return id;
}
