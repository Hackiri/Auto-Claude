import { useMemo, useState, useCallback } from 'react';
import type { TaskLogEntry } from '../../shared/types';
import type { LogFilterOptions, LogEntryType, ErrorPattern } from '../../shared/types/agent-session';
import { DEFAULT_LOG_FILTER } from '../../shared/types/agent-session';

/**
 * Map TaskLogEntryType to LogEntryType for filtering
 */
function mapLogType(type: TaskLogEntry['type']): LogEntryType {
  switch (type) {
    case 'error':
      return 'error';
    case 'phase_start':
    case 'phase_end':
      return 'phase';
    case 'tool_start':
    case 'tool_end':
      return 'tool';
    case 'success':
    case 'info':
      return 'info';
    default:
      return 'info';
  }
}

/**
 * Check if a log entry matches the given filter options
 */
function matchesFilter(entry: TaskLogEntry, filter: LogFilterOptions): boolean {
  // Type filter
  if (filter.types.length > 0) {
    const entryType = mapLogType(entry.type);
    if (!filter.types.includes(entryType)) {
      return false;
    }
  }

  // Phase filter
  if (filter.phase !== null && entry.phase !== filter.phase) {
    return false;
  }

  // Text search
  if (filter.searchText.trim()) {
    const search = filter.searchText.toLowerCase();
    const contentMatch = entry.content.toLowerCase().includes(search);
    const detailMatch = entry.detail?.toLowerCase().includes(search) ?? false;
    const toolMatch = entry.tool_name?.toLowerCase().includes(search) ?? false;
    if (!contentMatch && !detailMatch && !toolMatch) {
      return false;
    }
  }

  // Date range filter
  if (filter.dateRange) {
    const entryTime = new Date(entry.timestamp).getTime();
    const from = new Date(filter.dateRange.from).getTime();
    const to = new Date(filter.dateRange.to).getTime();
    if (entryTime < from || entryTime > to) {
      return false;
    }
  }

  return true;
}

/**
 * Common error patterns to detect in log content
 */
const ERROR_PATTERNS = [
  /TypeError:\s+(.+)/,
  /SyntaxError:\s+(.+)/,
  /ReferenceError:\s+(.+)/,
  /ENOENT:\s+(.+)/,
  /EACCES:\s+(.+)/,
  /ModuleNotFoundError:\s+(.+)/,
  /ImportError:\s+(.+)/,
  /command not found/i,
  /permission denied/i,
  /exit code \d+/i,
  /failed to/i,
  /compilation error/i,
  /build failed/i,
  /test failed/i,
];

/**
 * Detect error patterns across log entries
 */
function detectErrorPatterns(logs: TaskLogEntry[]): ErrorPattern[] {
  const patternMap = new Map<string, { count: number; first: number; last: number }>();

  for (let i = 0; i < logs.length; i++) {
    const entry = logs[i];
    if (entry.type !== 'error') continue;

    for (const regex of ERROR_PATTERNS) {
      const match = entry.content.match(regex);
      if (match) {
        const key = match[1] ? `${regex.source.split('\\s')[0].replace(/[\\:]/g, '')}: ${match[1].slice(0, 80)}` : match[0].slice(0, 80);
        const existing = patternMap.get(key);
        if (existing) {
          existing.count++;
          existing.last = i;
        } else {
          patternMap.set(key, { count: 1, first: i, last: i });
        }
        break; // Only match first pattern per entry
      }
    }
  }

  return Array.from(patternMap.entries())
    .map(([pattern, data]) => ({
      pattern,
      count: data.count,
      firstOccurrence: data.first,
      lastOccurrence: data.last,
    }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Extract unique phases from logs
 */
function extractPhases(logs: TaskLogEntry[]): string[] {
  const phases = new Set<string>();
  for (const log of logs) {
    if (log.phase) {
      phases.add(log.phase);
    }
  }
  return Array.from(phases);
}

/**
 * Hook for filtering and searching session logs with error pattern detection.
 *
 * Provides filter state management, filtered results, detected error patterns,
 * and available phases for the filter UI.
 */
export function useLogFilter(logs: TaskLogEntry[]) {
  const [filter, setFilter] = useState<LogFilterOptions>(DEFAULT_LOG_FILTER);

  const filteredLogs = useMemo(() => {
    return logs.filter((entry) => matchesFilter(entry, filter));
  }, [logs, filter]);

  const errorPatterns = useMemo(() => {
    return detectErrorPatterns(logs);
  }, [logs]);

  const availablePhases = useMemo(() => {
    return extractPhases(logs);
  }, [logs]);

  const setSearchText = useCallback((searchText: string) => {
    setFilter((prev) => ({ ...prev, searchText }));
  }, []);

  const setPhaseFilter = useCallback((phase: string | null) => {
    setFilter((prev) => ({ ...prev, phase }));
  }, []);

  const toggleTypeFilter = useCallback((type: LogEntryType) => {
    setFilter((prev) => {
      const types = prev.types.includes(type)
        ? prev.types.filter((t) => t !== type)
        : [...prev.types, type];
      return { ...prev, types };
    });
  }, []);

  const setDateRange = useCallback((dateRange: LogFilterOptions['dateRange']) => {
    setFilter((prev) => ({ ...prev, dateRange }));
  }, []);

  const resetFilter = useCallback(() => {
    setFilter(DEFAULT_LOG_FILTER);
  }, []);

  const hasActiveFilter = useMemo(() => {
    return (
      filter.types.length > 0 ||
      filter.phase !== null ||
      filter.searchText.trim() !== '' ||
      filter.dateRange !== undefined
    );
  }, [filter]);

  return {
    filter,
    setFilter,
    filteredLogs,
    errorPatterns,
    availablePhases,
    hasActiveFilter,
    setSearchText,
    setPhaseFilter,
    toggleTypeFilter,
    setDateRange,
    resetFilter,
    totalCount: logs.length,
    filteredCount: filteredLogs.length,
  };
}
