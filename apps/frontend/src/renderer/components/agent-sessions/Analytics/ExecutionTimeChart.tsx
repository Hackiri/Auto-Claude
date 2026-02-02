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
  Cell,
} from 'recharts';
import type { ExecutionTimeDataPoint } from '../../../../shared/types/agent-session';

interface ExecutionTimeChartProps {
  data: ExecutionTimeDataPoint[];
}

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function ExecutionTimeChart({ data }: ExecutionTimeChartProps) {
  const { t } = useTranslation('agentSessions');

  const chartData = useMemo(() => {
    // Show last 20 sessions to keep chart readable
    const recent = data.slice(-20);
    return recent.map((d, i) => ({
      ...d,
      label: d.title.length > 15 ? `${d.title.slice(0, 15)}…` : d.title,
      durationMinutes: d.durationMs / 60000,
      index: i,
    }));
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
          tickFormatter={(v: number) => `${Math.round(v)}m`}
          width={35}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            fontSize: '12px',
          }}
          labelStyle={{ color: 'var(--foreground)' }}
          formatter={(value: number) => [formatDuration(value * 60000), t('analytics.duration')]}
          labelFormatter={(label: string) => label}
        />
        <Bar dataKey="durationMinutes" radius={[4, 4, 0, 0]} maxBarSize={40}>
          {chartData.map((entry) => (
            <Cell
              key={entry.sessionId}
              fill={entry.success ? '#22c55e' : '#ef4444'}
              fillOpacity={0.8}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
