import { useTranslation } from 'react-i18next';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';
import type { SuccessRateDataPoint } from '../../../../shared/types/agent-session';

interface SuccessRateChartProps {
  data: SuccessRateDataPoint[];
}

export function SuccessRateChart({ data }: SuccessRateChartProps) {
  const { t } = useTranslation('agentSessions');

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        {t('analytics.noData')}
      </div>
    );
  }

  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius="55%"
          outerRadius="80%"
          paddingAngle={2}
          dataKey="value"
          nameKey="name"
          strokeWidth={0}
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            fontSize: '12px',
          }}
          formatter={(value: number, name: string) => {
            const pct = total > 0 ? Math.round((value / total) * 100) : 0;
            return [`${value} (${pct}%)`, name];
          }}
        />
        <Legend
          verticalAlign="bottom"
          height={24}
          iconType="circle"
          iconSize={8}
          formatter={(value: string) => (
            <span style={{ color: 'var(--muted-foreground)', fontSize: '11px' }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
