import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { PhaseDurationDataPoint } from '../../../../shared/types/agent-session';

interface PhaseDurationChartProps {
  data: PhaseDurationDataPoint[];
}

const PHASE_COLORS = [
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#f97316', // orange
  '#ec4899', // pink
];

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function PhaseDurationChart({ data }: PhaseDurationChartProps) {
  const { t } = useTranslation('agentSessions');

  const { chartData, phaseKeys } = useMemo(() => {
    const recent = data.slice(-10);
    const keys = new Set<string>();

    for (const entry of recent) {
      for (const key of Object.keys(entry)) {
        if (key !== 'sessionTitle') {
          keys.add(key);
        }
      }
    }

    const processed = recent.map((d) => ({
      ...d,
      label:
        d.sessionTitle.length > 12
          ? `${d.sessionTitle.slice(0, 12)}…`
          : d.sessionTitle,
    }));

    return { chartData: processed, phaseKeys: Array.from(keys) };
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        {t('analytics.noData')}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => formatDuration(v)}
          width={45}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            fontSize: '12px',
          }}
          labelStyle={{ color: 'var(--foreground)' }}
          formatter={(value: number, name: string) => [formatDuration(value), name]}
        />
        <Legend
          wrapperStyle={{ fontSize: '10px' }}
          formatter={(value: string) => (
            <span style={{ color: 'var(--foreground)' }}>{value}</span>
          )}
        />
        {phaseKeys.map((phase, i) => (
          <Bar
            key={phase}
            dataKey={phase}
            stackId="phases"
            fill={PHASE_COLORS[i % PHASE_COLORS.length]}
            fillOpacity={0.8}
            radius={i === phaseKeys.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
