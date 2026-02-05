import { create } from 'zustand';
import type {
  SessionHistoryEntry,
  SessionMetrics,
  ExecutionTimeDataPoint,
  SuccessRateDataPoint,
  PhaseDurationDataPoint,
  TrendDataPoint
} from '../../shared/types';
import { debugLog } from '../../shared/utils/debug-logger';

interface SessionAnalyticsState {
  // Data
  executionTimeData: ExecutionTimeDataPoint[];
  successRateData: SuccessRateDataPoint[];
  phaseDurationData: PhaseDurationDataPoint[];
  trendData: TrendDataPoint[];
  metrics: SessionMetrics | null;
  isComputing: boolean;

  // Actions
  computeFromHistory: (entries: SessionHistoryEntry[]) => void;
  setMetrics: (metrics: SessionMetrics | null) => void;
  clear: () => void;

  // Selectors
  getSuccessRate: () => number;
  getAverageDurationMs: () => number;
  getTotalSessions: () => number;
}

/**
 * Compute execution time chart data from history entries.
 * Sorted by completion date ascending, capped at 100 most recent.
 */
function computeExecutionTimeData(entries: SessionHistoryEntry[]): ExecutionTimeDataPoint[] {
  // Filter to only entries with completedAt, then type-narrow to ensure completedAt is defined
  const completedEntries = entries.filter(
    (e): e is SessionHistoryEntry & { completedAt: string } => e.completedAt !== undefined && e.completedAt !== null
  );

  return completedEntries
    .sort((a, b) => new Date(a.completedAt).getTime() - new Date(b.completedAt).getTime())
    .slice(-100)
    .map((e) => ({
      sessionId: e.id,
      title: e.title.length > 30 ? e.title.substring(0, 27) + '...' : e.title,
      durationMs: e.durationMs,
      completedAt: e.completedAt,
      success: e.success
    }));
}

/**
 * Compute success rate pie chart data.
 */
function computeSuccessRateData(entries: SessionHistoryEntry[]): SuccessRateDataPoint[] {
  const completed = entries.filter((e) => e.completedAt);
  if (completed.length === 0) return [];

  const successCount = completed.filter((e) => e.success).length;
  const failureCount = completed.length - successCount;

  const data: SuccessRateDataPoint[] = [];

  if (successCount > 0) {
    data.push({ name: 'Success', value: successCount, color: '#22c55e' });
  }
  if (failureCount > 0) {
    data.push({ name: 'Failed', value: failureCount, color: '#ef4444' });
  }

  return data;
}

/**
 * Compute phase duration stacked bar chart data.
 * Aggregates phase durations across sessions, capped at 50 most recent.
 */
function computePhaseDurationData(entries: SessionHistoryEntry[]): PhaseDurationDataPoint[] {
  return entries
    .filter((e) => e.phaseDurations && e.phaseDurations.length > 0)
    .sort((a, b) => new Date(a.completedAt || a.createdAt).getTime() - new Date(b.completedAt || b.createdAt).getTime())
    .slice(-50)
    .map((e) => {
      const point: PhaseDurationDataPoint = {
        sessionTitle: e.title.length > 20 ? e.title.substring(0, 17) + '...' : e.title
      };
      for (const pd of e.phaseDurations) {
        point[pd.phase] = pd.durationMs;
      }
      return point;
    });
}

/**
 * Compute trend data aggregated by day.
 * Groups sessions by completion date and computes daily averages.
 */
function computeTrendData(entries: SessionHistoryEntry[]): TrendDataPoint[] {
  const completed = entries.filter((e) => e.completedAt);
  if (completed.length === 0) return [];

  // Group by day
  const dayMap = new Map<string, SessionHistoryEntry[]>();

  for (const entry of completed) {
    const day = entry.completedAt?.substring(0, 10); // YYYY-MM-DD
    const existing = dayMap.get(day);
    if (existing) {
      existing.push(entry);
    } else {
      dayMap.set(day, [entry]);
    }
  }

  // Convert to trend data points, sorted by date
  const trendPoints: TrendDataPoint[] = [];

  const sortedDays = Array.from(dayMap.keys()).sort();
  for (const day of sortedDays) {
    const daySessions = dayMap.get(day);
    if (!daySessions) continue; // Should never happen since we iterate over keys, but satisfies type checker
    const totalDuration = daySessions.reduce((sum, e) => sum + e.durationMs, 0);
    const successCount = daySessions.filter((e) => e.success).length;

    trendPoints.push({
      date: day,
      averageDurationMs: Math.round(totalDuration / daySessions.length),
      successRate: daySessions.length > 0 ? successCount / daySessions.length : 0,
      sessionCount: daySessions.length
    });
  }

  // Cap at 90 days of data
  return trendPoints.slice(-90);
}

/**
 * Compute aggregate metrics from history entries.
 */
function computeMetrics(entries: SessionHistoryEntry[]): SessionMetrics {
  const completed = entries.filter((e) => e.completedAt);
  const successCount = completed.filter((e) => e.success).length;
  const failureCount = completed.length - successCount;

  // Durations
  const durations = completed.map((e) => e.durationMs).sort((a, b) => a - b);
  const totalDuration = durations.reduce((sum, d) => sum + d, 0);
  const averageDurationMs = durations.length > 0 ? Math.round(totalDuration / durations.length) : 0;
  const medianDurationMs = durations.length > 0
    ? durations.length % 2 === 0
      ? Math.round((durations[durations.length / 2 - 1] + durations[durations.length / 2]) / 2)
      : durations[Math.floor(durations.length / 2)]
    : 0;

  // Average phase durations
  const phaseAccum = new Map<string, { total: number; count: number }>();
  for (const entry of completed) {
    if (!entry.phaseDurations) continue;
    for (const pd of entry.phaseDurations) {
      const existing = phaseAccum.get(pd.phase);
      if (existing) {
        existing.total += pd.durationMs;
        existing.count += 1;
      } else {
        phaseAccum.set(pd.phase, { total: pd.durationMs, count: 1 });
      }
    }
  }

  const averagePhaseDurations: Record<string, number> = {};
  for (const [phase, data] of phaseAccum) {
    averagePhaseDurations[phase] = Math.round(data.total / data.count);
  }

  return {
    totalSessions: completed.length,
    successCount,
    failureCount,
    successRate: completed.length > 0 ? successCount / completed.length : 0,
    averageDurationMs,
    medianDurationMs,
    averagePhaseDurations
  };
}

export const useSessionAnalyticsStore = create<SessionAnalyticsState>((set, get) => ({
  // Initial state
  executionTimeData: [],
  successRateData: [],
  phaseDurationData: [],
  trendData: [],
  metrics: null,
  isComputing: false,

  // Actions
  computeFromHistory: (entries) => {
    set({ isComputing: true });

    try {
      const executionTimeData = computeExecutionTimeData(entries);
      const successRateData = computeSuccessRateData(entries);
      const phaseDurationData = computePhaseDurationData(entries);
      const trendData = computeTrendData(entries);
      const metrics = computeMetrics(entries);

      set({
        executionTimeData,
        successRateData,
        phaseDurationData,
        trendData,
        metrics,
        isComputing: false
      });
    } catch (err) {
      debugLog('[SessionAnalyticsStore] Error computing analytics:', err);
      set({ isComputing: false });
    }
  },

  setMetrics: (metrics) => set({ metrics }),

  clear: () =>
    set({
      executionTimeData: [],
      successRateData: [],
      phaseDurationData: [],
      trendData: [],
      metrics: null,
      isComputing: false
    }),

  // Selectors
  getSuccessRate: () => {
    const { metrics } = get();
    return metrics?.successRate ?? 0;
  },

  getAverageDurationMs: () => {
    const { metrics } = get();
    return metrics?.averageDurationMs ?? 0;
  },

  getTotalSessions: () => {
    const { metrics } = get();
    return metrics?.totalSessions ?? 0;
  }
}));
