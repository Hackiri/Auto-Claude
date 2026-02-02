import { useTranslation } from 'react-i18next';
import { Search, Filter, X } from 'lucide-react';
import { Input } from '../../ui/input';
import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import type { LogFilterOptions, LogEntryType } from '../../../../shared/types/agent-session';

interface LogFilterBarProps {
  filters: LogFilterOptions;
  onFiltersChange: (filters: LogFilterOptions) => void;
  availablePhases: string[];
  matchCount?: number;
}

const LOG_TYPES: LogEntryType[] = ['error', 'info', 'phase', 'tool'];

export function LogFilterBar({ filters, onFiltersChange, availablePhases, matchCount }: LogFilterBarProps) {
  const { t } = useTranslation('agentSessions');

  const hasActiveFilters = filters.types.length > 0 || filters.phase !== null || filters.searchText !== '';

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, searchText: value });
  };

  const handleTypeChange = (value: string) => {
    if (value === 'all') {
      onFiltersChange({ ...filters, types: [] });
    } else {
      const type = value as LogEntryType;
      const types = filters.types.includes(type)
        ? filters.types.filter((t) => t !== type)
        : [...filters.types, type];
      onFiltersChange({ ...filters, types });
    }
  };

  const handlePhaseChange = (value: string) => {
    onFiltersChange({ ...filters, phase: value === 'all' ? null : value });
  };

  const handleClearFilters = () => {
    onFiltersChange({ types: [], phase: null, searchText: '' });
  };

  const getTypeLabel = (type: LogEntryType): string => {
    switch (type) {
      case 'error': return t('logFilter.typeError');
      case 'info': return t('logFilter.typeInfo');
      case 'phase': return t('logFilter.typePhase');
      case 'tool': return t('logFilter.typeTool');
      default: return type;
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-muted/30 border-t border-border">
      {/* Search input */}
      <div className="relative flex-1 min-w-[120px] max-w-[240px]">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={filters.searchText}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder={t('logFilter.searchPlaceholder')}
          className="h-7 pl-7 pr-2 text-xs bg-background"
        />
      </div>

      {/* Type filter */}
      <Select value={filters.types.length === 1 ? filters.types[0] : 'all'} onValueChange={handleTypeChange}>
        <SelectTrigger className="h-7 w-[120px] text-xs bg-background">
          <Filter className="h-3 w-3 mr-1 text-muted-foreground" />
          <SelectValue placeholder={t('logFilter.filterByType')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('logFilter.allTypes')}</SelectItem>
          {LOG_TYPES.map((type) => (
            <SelectItem key={type} value={type}>
              {getTypeLabel(type)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Phase filter */}
      {availablePhases.length > 0 && (
        <Select value={filters.phase ?? 'all'} onValueChange={handlePhaseChange}>
          <SelectTrigger className="h-7 w-[120px] text-xs bg-background">
            <SelectValue placeholder={t('logFilter.filterByPhase')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('logFilter.allPhases')}</SelectItem>
            {availablePhases.map((phase) => (
              <SelectItem key={phase} value={phase}>
                {phase}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Active filter badges */}
      {filters.types.length > 1 && (
        <div className="flex items-center gap-1">
          {filters.types.map((type) => (
            <Badge
              key={type}
              variant="secondary"
              className="text-[10px] px-1.5 py-0 h-5 cursor-pointer hover:bg-destructive/20"
              onClick={() => handleTypeChange(type)}
            >
              {getTypeLabel(type)}
              <X className="h-2.5 w-2.5 ml-1" />
            </Badge>
          ))}
        </div>
      )}

      {/* Match count */}
      {hasActiveFilters && matchCount !== undefined && (
        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
          {t('logFilter.matchCount', { count: matchCount })}
        </span>
      )}

      {/* Clear filters */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs gap-1 px-2"
          onClick={handleClearFilters}
        >
          <X className="h-3 w-3" />
          {t('logFilter.clearFilters')}
        </Button>
      )}
    </div>
  );
}
