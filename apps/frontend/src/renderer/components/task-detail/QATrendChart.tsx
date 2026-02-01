import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  CalendarDays,
  Percent,
  Info
} from 'lucide-react';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { cn } from '../../lib/utils';
import type { QATrendDataPoint, QATrendData } from '../../../shared/types';

interface QATrendChartProps {
  trendData: QATrendData | null;
  className?: string;
}

// Format date for display (e.g., "Jan 15")
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  });
}

// Format date for tooltip (e.g., "January 15, 2024")
function formatDateFull(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  });
}

// Calculate trend direction from data points
function calculateTrend(dataPoints: QATrendDataPoint[]): 'up' | 'down' | 'stable' {
  if (dataPoints.length < 2) return 'stable';

  const recent = dataPoints.slice(-3);
  const first = recent[0]?.passRate ?? 0;
  const last = recent[recent.length - 1]?.passRate ?? 0;

  const diff = last - first;
  if (diff > 5) return 'up';
  if (diff < -5) return 'down';
  return 'stable';
}

// Get color for pass rate
function getPassRateColor(rate: number): string {
  if (rate >= 80) return 'var(--success)';
  if (rate >= 60) return 'var(--warning)';
  return 'var(--error)';
}

// SVG Line Chart Component
interface LineChartProps {
  dataPoints: QATrendDataPoint[];
  width: number;
  height: number;
  onHover: (point: QATrendDataPoint | null, x: number, y: number) => void;
}

function LineChart({ dataPoints, width, height, onHover }: LineChartProps) {
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Calculate scales
  const xScale = useMemo(() => {
    if (dataPoints.length === 0) return { min: 0, max: 1, range: chartWidth };
    return {
      min: 0,
      max: dataPoints.length - 1,
      range: chartWidth
    };
  }, [dataPoints.length, chartWidth]);

  const yScale = useMemo(() => ({
    min: 0,
    max: 100,
    range: chartHeight
  }), [chartHeight]);

  // Convert data point to SVG coordinates
  const pointToCoord = (point: QATrendDataPoint, index: number) => {
    const x = padding.left + (index / Math.max(xScale.max, 1)) * xScale.range;
    const y = padding.top + chartHeight - (point.passRate / yScale.max) * yScale.range;
    return { x, y };
  };

  // Generate path for line chart
  const linePath = useMemo(() => {
    if (dataPoints.length === 0) return '';

    return dataPoints
      .map((point, i) => {
        const { x, y } = pointToCoord(point, i);
        return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
      })
      .join(' ');
  }, [dataPoints, pointToCoord]);

  // Generate area fill path
  const areaPath = useMemo(() => {
    if (dataPoints.length === 0) return '';

    const linePoints = dataPoints.map((point, i) => {
      const { x, y } = pointToCoord(point, i);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');

    const lastX = padding.left + chartWidth;
    const firstX = padding.left;
    const bottomY = padding.top + chartHeight;

    return `${linePoints} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;
  }, [dataPoints, pointToCoord, chartWidth, chartHeight, padding]);

  // Y-axis ticks
  const yTicks = [0, 25, 50, 75, 100];

  // X-axis labels (show every nth label to avoid overlap)
  const xLabelInterval = Math.max(1, Math.floor(dataPoints.length / 5));

  if (dataPoints.length === 0) {
    return (
      <svg width={width} height={height} className="overflow-visible">
        <text
          x={width / 2}
          y={height / 2}
          textAnchor="middle"
          className="fill-muted-foreground text-sm"
        >
          No data available
        </text>
      </svg>
    );
  }

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Background grid */}
      <g className="stroke-border/30">
        {yTicks.map(tick => {
          const y = padding.top + chartHeight - (tick / 100) * chartHeight;
          return (
            <line
              key={tick}
              x1={padding.left}
              y1={y}
              x2={padding.left + chartWidth}
              y2={y}
              strokeDasharray="4,4"
            />
          );
        })}
      </g>

      {/* Y-axis labels */}
      <g className="fill-muted-foreground text-xs">
        {yTicks.map(tick => {
          const y = padding.top + chartHeight - (tick / 100) * chartHeight;
          return (
            <text
              key={tick}
              x={padding.left - 8}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
              className="text-[10px]"
            >
              {tick}%
            </text>
          );
        })}
      </g>

      {/* X-axis labels */}
      <g className="fill-muted-foreground text-xs">
        {dataPoints.map((point, i) => {
          if (i % xLabelInterval !== 0 && i !== dataPoints.length - 1) return null;
          const { x } = pointToCoord(point, i);
          return (
            <text
              key={point.date}
              x={x}
              y={padding.top + chartHeight + 20}
              textAnchor="middle"
              className="text-[10px]"
            >
              {formatDate(point.date)}
            </text>
          );
        })}
      </g>

      {/* Gradient definition */}
      <defs>
        <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Area fill */}
      <path
        d={areaPath}
        fill="url(#areaGradient)"
        className="transition-all duration-300"
      />

      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="transition-all duration-300"
      />

      {/* Data points */}
      {dataPoints.map((point, i) => {
        const { x, y } = pointToCoord(point, i);
        return (
          <g
            key={point.date}
            className="cursor-pointer"
            onMouseEnter={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              onHover(point, rect.left + rect.width / 2, rect.top);
            }}
            onMouseLeave={() => onHover(null, 0, 0)}
          >
            {/* Larger hit area */}
            <circle
              cx={x}
              cy={y}
              r={12}
              fill="transparent"
            />
            {/* Visible point */}
            <circle
              cx={x}
              cy={y}
              r={4}
              fill="var(--background)"
              stroke={getPassRateColor(point.passRate)}
              strokeWidth="2"
              className="transition-all duration-200 hover:r-6"
            />
          </g>
        );
      })}
    </svg>
  );
}

export function QATrendChart({ trendData, className }: QATrendChartProps) {
  const { t } = useTranslation(['tasks']);
  const [hoveredPoint, setHoveredPoint] = useState<{
    point: QATrendDataPoint;
    x: number;
    y: number;
  } | null>(null);

  // Calculate chart dimensions based on container
  const chartHeight = 200;

  // Extract data points
  const dataPoints = trendData?.dataPoints ?? [];
  const overallPassRate = trendData?.overallPassRate ?? 0;
  const totalTasksValidated = trendData?.totalTasksValidated ?? 0;

  // Calculate trend direction
  const trend = calculateTrend(dataPoints);

  // Handle hover
  const handleHover = (point: QATrendDataPoint | null, x: number, y: number) => {
    if (point) {
      setHoveredPoint({ point, x, y });
    } else {
      setHoveredPoint(null);
    }
  };

  // Empty state
  if (!trendData || dataPoints.length === 0) {
    return (
      <div className={cn('p-4', className)}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            {t('tasks:qa.trends.title')}
          </h3>
        </div>
        <div className="h-[200px] flex items-center justify-center bg-muted/30 rounded-lg border border-dashed border-border">
          <div className="text-center">
            <BarChart3 className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
            <p className="text-sm font-medium text-muted-foreground mb-1">
              {t('tasks:qa.trends.noTrendData')}
            </p>
            <p className="text-xs text-muted-foreground/70">
              {t('tasks:qa.dashboard.noDataDescription')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          {t('tasks:qa.trends.title')}
        </h3>
        <div className="flex items-center gap-2">
          {/* Trend indicator */}
          <Badge
            variant="outline"
            className={cn(
              'text-xs flex items-center gap-1',
              trend === 'up' && 'text-success border-success/30 bg-success/10',
              trend === 'down' && 'text-destructive border-destructive/30 bg-destructive/10',
              trend === 'stable' && 'text-muted-foreground border-border bg-muted/30'
            )}
          >
            {trend === 'up' && <TrendingUp className="h-3 w-3" />}
            {trend === 'down' && <TrendingDown className="h-3 w-3" />}
            {trend === 'stable' && <Minus className="h-3 w-3" />}
            {t(`tasks:qa.trends.${trend === 'up' ? 'improvement' : trend === 'down' ? 'regression' : 'stable'}`)}
          </Badge>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-muted/30 rounded-lg p-2.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
            <Percent className="h-3 w-3" />
            <span className="text-[10px] uppercase tracking-wider">
              {t('tasks:qa.trends.passRate')}
            </span>
          </div>
          <p className={cn(
            'text-lg font-semibold tabular-nums',
            overallPassRate >= 80 ? 'text-success' :
            overallPassRate >= 60 ? 'text-warning' : 'text-destructive'
          )}>
            {Math.round(overallPassRate)}%
          </p>
        </div>
        <div className="bg-muted/30 rounded-lg p-2.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
            <CalendarDays className="h-3 w-3" />
            <span className="text-[10px] uppercase tracking-wider">
              {t('tasks:qa.dashboard.totalRuns')}
            </span>
          </div>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {totalTasksValidated}
          </p>
        </div>
        <div className="bg-muted/30 rounded-lg p-2.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
            <BarChart3 className="h-3 w-3" />
            <span className="text-[10px] uppercase tracking-wider">
              {t('tasks:qa.trends.averageIterations')}
            </span>
          </div>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {dataPoints.length > 0
              ? (
                  dataPoints.reduce((sum, p) => sum + (p.avgIterationsToPass ?? 1), 0) /
                  dataPoints.length
                ).toFixed(1)
              : '-'}
          </p>
        </div>
      </div>

      {/* Chart */}
      <div className="relative bg-card rounded-lg border border-border p-3">
        {/* Chart title */}
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-muted-foreground">
            {t('tasks:qa.trends.passRateOverTime')}
          </span>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="h-3 w-3 text-muted-foreground/50 cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-xs">{t('tasks:qa.trends.chartLabel')}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* SVG Chart */}
        <div className="w-full" style={{ height: chartHeight }}>
          <LineChart
            dataPoints={dataPoints}
            width={400}
            height={chartHeight}
            onHover={handleHover}
          />
        </div>

        {/* Hover tooltip */}
        {hoveredPoint && (
          <div
            className="fixed z-50 pointer-events-none"
            style={{
              left: hoveredPoint.x,
              top: hoveredPoint.y - 10,
              transform: 'translate(-50%, -100%)'
            }}
          >
            <div className="bg-popover text-popover-foreground shadow-lg rounded-lg border border-border p-2.5 text-xs">
              <p className="font-medium mb-1">{formatDateFull(hoveredPoint.point.date)}</p>
              <div className="space-y-0.5">
                <p className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">{t('tasks:qa.trends.passRate')}:</span>
                  <span className={cn(
                    'font-semibold',
                    hoveredPoint.point.passRate >= 80 ? 'text-success' :
                    hoveredPoint.point.passRate >= 60 ? 'text-warning' : 'text-destructive'
                  )}>
                    {Math.round(hoveredPoint.point.passRate)}%
                  </span>
                </p>
                <p className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">{t('tasks:qa.criteria.passed')}:</span>
                  <span className="text-success">{hoveredPoint.point.passedTasks}</span>
                </p>
                <p className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">{t('tasks:qa.criteria.failed')}:</span>
                  <span className="text-destructive">{hoveredPoint.point.failedTasks}</span>
                </p>
                <p className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">{t('tasks:qa.criteria.total')}:</span>
                  <span>{hoveredPoint.point.totalTasks}</span>
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 rounded bg-primary" />
          <span>{t('tasks:qa.trends.passRate')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full border-2 border-success bg-background" />
          <span>≥80%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full border-2 border-warning bg-background" />
          <span>60-79%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full border-2 border-destructive bg-background" />
          <span>&lt;60%</span>
        </div>
      </div>
    </div>
  );
}
