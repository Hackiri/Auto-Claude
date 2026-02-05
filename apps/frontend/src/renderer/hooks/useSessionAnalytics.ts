import { useMemo } from 'react';
import { useAgentSessionsStore } from '../stores/agent-sessions-store';
import type { AgentSession } from '../../shared/types';
import type {
  SessionMetrics,
  ExecutionTimeDataPoint,
  SuccessRateDataPoint,
  PhaseDurationDataPoint,
  TrendDataPoint,
  SessionHistoryEntry,
} from '../../shared/types/agent-session';

/**
 * Compute median from a sorted array of numbers
 */
function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Derive SessionMetrics from a list of completed sessions
 */
function computeMetrics(sessions: AgentSession[]): SessionMetrics {
  const completed = sessions.filter(
    (s) => s.status === 'completed' || s.status === 'failed' || s.status === 'archived'
  );

  const totalSessions = completed.length;
  const successCount = completed.filter((s) => s.status === 'completed').length;
  const failureCount = completed.filter((s) => s.status === 'failed').length;
  const successRate = totalSessions > 0 ? successCount / totalSessions : 0;

  const durations = completed
    .map((s) => {
      if (s.startedAt && s.completedAt) {
        return s.completedAt.getTime() - s.startedAt.getTime();
      }
      return 0;
    })
    .filter((d) => d > 0);

  const averageDurationMs =
    durations.length > 0 ? durations.reduce((a, b) => a + b, 0) / durations.length : 0;
  const medianDurationMs = median(durations);

  // Compute average phase durations from history entries if available
  const phaseDurationAccum: Record<string, { total: number; count: number }> = {};
  for (const session of completed) {
    const history = session as unknown as SessionHistoryEntry;
    if (history.phaseDurations && Array.isArray(history.phaseDurations)) {
      for (const pd of history.phaseDurations) {
        const key = pd.phase;
        if (!phaseDurationAccum[key]) {
          phaseDurationAccum[key] = { total: 0, count: 0 };
        }
        phaseDurationAccum[key].total += pd.durationMs;
        phaseDurationAccum[key].count++;
      }
    }
  }

  const averagePhaseDurations: Record<string, number> = {};
  for (const [phase, data] of Object.entries(phaseDurationAccum)) {
    averagePhaseDurations[phase] = data.count > 0 ? data.total / data.count : 0;
  }

  return {
    totalSessions,
    successCount,
    failureCount,
    successRate,
    averageDurationMs,
    medianDurationMs,
    averagePhaseDurations,
  };
}

/**
 * Derive execution time chart data from sessions
 */
function computeExecutionTimeData(sessions: AgentSession[]): ExecutionTimeDataPoint[] {
  return sessions
    .filter((s): s is AgentSession & { startedAt: Date; completedAt: Date } =>
      s.startedAt != null && s.completedAt != null
    )
    .map((s) => ({
      sessionId: s.id,
      title: s.title || s.specId || s.id,
      durationMs: s.completedAt.getTime() - s.startedAt.getTime(),
      completedAt: s.completedAt.toISOString(),
      success: s.status === 'completed',
    }))
    .sort((a, b) => new Date(a.completedAt).getTime() - new Date(b.completedAt).getTime());
}

/**
 * Derive success rate pie chart data
 */
function computeSuccessRateData(metrics: SessionMetrics): SuccessRateDataPoint[] {
  if (metrics.totalSessions === 0) return [];

  const other = metrics.totalSessions - metrics.successCount - metrics.failureCount;
  const points: SuccessRateDataPoint[] = [
    { name: 'Success', value: metrics.successCount, color: '#22c55e' },
    { name: 'Failed', value: metrics.failureCount, color: '#ef4444' },
  ];

  if (other > 0) {
    points.push({ name: 'Other', value: other, color: '#94a3b8' });
  }

  return points.filter((p) => p.value > 0);
}

/**
 * Derive phase duration stacked bar chart data
 */
function computePhaseDurationData(sessions: AgentSession[]): PhaseDurationDataPoint[] {
  return sessions
    .filter((s) => {
      const history = s as unknown as SessionHistoryEntry;
      return history.phaseDurations && Array.isArray(history.phaseDurations) && history.phaseDurations.length > 0;
    })
    .map((s) => {
      const history = s as unknown as SessionHistoryEntry;
      const point: PhaseDurationDataPoint = {
        sessionTitle: s.title || s.specId || s.id,
      };
      for (const pd of history.phaseDurations) {
        point[pd.phase] = pd.durationMs;
      }
      return point;
    });
}

/**
 * Derive trend data grouped by day
 */
function computeTrendData(sessions: AgentSession[]): TrendDataPoint[] {
  const completed = sessions.filter((s) => s.completedAt);
  if (completed.length === 0) return [];

  const byDay = new Map<string, { durations: number[]; successes: number; total: number }>();

  for (const s of completed) {
    const day = s.completedAt?.toISOString().slice(0, 10); // YYYY-MM-DD
    if (!day) continue; // Skip if completedAt is undefined
    if (!byDay.has(day)) {
      byDay.set(day, { durations: [], successes: 0, total: 0 });
    }
    const bucket = byDay.get(day);
    if (!bucket) continue; // TypeScript guard (should never happen after set)
    bucket.total++;
    if (s.status === 'completed') bucket.successes++;
    if (s.startedAt && s.completedAt) {
      const dur = s.completedAt.getTime() - s.startedAt.getTime();
      if (dur > 0) bucket.durations.push(dur);
    }
  }

  return Array.from(byDay.entries())
    .map(([date, data]) => ({
      date,
      averageDurationMs:
        data.durations.length > 0
          ? data.durations.reduce((a, b) => a + b, 0) / data.durations.length
          : 0,
      successRate: data.total > 0 ? data.successes / data.total : 0,
      sessionCount: data.total,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * Hook that derives analytics chart data and metrics from the session store.
 *
 * Computes metrics, execution time series, success rate breakdown,
 * phase duration data, and daily trend data from all completed/archived sessions.
 */
export function useSessionAnalytics() {
  const sessions = useAgentSessionsStore((state) => state.sessions);

  const completedSessions = useMemo(() => {
    return sessions.filter(
      (s) => s.status === 'completed' || s.status === 'failed' || s.status === 'archived'
    );
  }, [sessions]);

  const metrics = useMemo(() => {
    return computeMetrics(completedSessions);
  }, [completedSessions]);

  const executionTimeData = useMemo(() => {
    return computeExecutionTimeData(completedSessions);
  }, [completedSessions]);

  const successRateData = useMemo(() => {
    return computeSuccessRateData(metrics);
  }, [metrics]);

  const phaseDurationData = useMemo(() => {
    return computePhaseDurationData(completedSessions);
  }, [completedSessions]);

  const trendData = useMemo(() => {
    return computeTrendData(completedSessions);
  }, [completedSessions]);

  return {
    metrics,
    executionTimeData,
    successRateData,
    phaseDurationData,
    trendData,
    hasData: completedSessions.length > 0,
    sessionCount: completedSessions.length,
  };
}
