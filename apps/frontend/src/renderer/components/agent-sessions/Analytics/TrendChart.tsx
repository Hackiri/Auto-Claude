import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { TrendDataPoint } from '../../../../shared/types/agent-session';

interface TrendChartProps {
  data: TrendDataPoint[];
}

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export function TrendChart({ data }: TrendChartProps) {
  const { t } = useTranslation('agentSessions');

  const chartData = useMemo(() => {
    return data.slice(-30).map((d) => ({
      ...d,
      label: formatDate(d.date),
      durationMinutes: d.averageDurationMs / 60000,
      successPct: Math.round(d.successRate * 100),
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
      <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          yAxisId="duration"
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${Math.round(v)}m`}
          width={35}
        />
        <YAxis
          yAxisId="rate"
          orientation="right"
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
          domain={[0, 100]}
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
          formatter={(value: number, name: string) => {
            if (name === t('analytics.avgDuration')) {
              return [formatDuration(value * 60000), name];
            }
            return [`${value}%`, name];
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: '10px' }}
          formatter={(value: string) => (
            <span style={{ color: 'var(--foreground)' }}>{value}</span>
          )}
        />
        <Line
          yAxisId="duration"
          type="monotone"
          dataKey="durationMinutes"
          name={t('analytics.avgDuration')}
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 3, fill: '#3b82f6' }}
          activeDot={{ r: 5 }}
        />
        <Line
          yAxisId="rate"
          type="monotone"
          dataKey="successPct"
          name={t('analytics.successRate')}
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ r: 3, fill: '#22c55e' }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
