import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Bot, Activity, History, Search } from 'lucide-react';
import { ScrollArea } from '../../ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../ui/tabs';
import { useAgentSessionsStore } from '../../../stores/agent-sessions-store';
import { useSessionHistoryStore } from '../../../stores/session-history-store';
import { SessionListItem } from './SessionListItem';
import { cn } from '../../../lib/utils';
import type { AgentSession, SessionHistoryEntry } from '../../../../shared/types';

export function SessionSidebar() {
  const { t } = useTranslation('agentSessions');
  const activeTab = useAgentSessionsStore((state) => state.activeTab);
  const setActiveTab = useAgentSessionsStore((state) => state.setActiveTab);
  const getActiveSessions = useAgentSessionsStore((state) => state.getActiveSessions);
  const getArchivedSessions = useAgentSessionsStore((state) => state.getArchivedSessions);

  const historySearchText = useSessionHistoryStore((state) => state.filters.searchText);
  const setHistorySearchText = useSessionHistoryStore((state) => state.setSearchText);
  const getFilteredEntries = useSessionHistoryStore((state) => state.getFilteredEntries);
  const isLoadingHistory = useSessionHistoryStore((state) => state.isLoading);

  const activeSessions = getActiveSessions();
  const archivedSessions = getArchivedSessions();
  const historyEntries = getFilteredEntries();

  const selectSession = useAgentSessionsStore((state) => state.selectSession);
  const selectedSessionId = useAgentSessionsStore((state) => state.selectedSessionId);

  // Count running sessions
  const runningSessions = activeSessions.filter(s => s.status === 'running').length;

  // Get current tab's session list for keyboard navigation
  const currentSessions: AgentSession[] = activeTab === 'active' ? activeSessions : activeTab === 'archived' ? archivedSessions : [];
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Reset focused index when tab or sessions change
  useEffect(() => {
    setFocusedIndex(-1);
  }, [activeTab, currentSessions.length]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Don't handle if inside an input
    if ((e.target as HTMLElement).tagName === 'INPUT') return;
    if (currentSessions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault();
        setFocusedIndex((prev) => {
          const next = prev < currentSessions.length - 1 ? prev + 1 : prev;
          return next;
        });
        break;
      }
      case 'ArrowUp': {
        e.preventDefault();
        setFocusedIndex((prev) => {
          const next = prev > 0 ? prev - 1 : 0;
          return next;
        });
        break;
      }
      case 'Enter': {
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < currentSessions.length) {
          selectSession(currentSessions[focusedIndex].id);
        }
        break;
      }
      case 'Escape': {
        e.preventDefault();
        selectSession(null);
        setFocusedIndex(-1);
        break;
      }
    }
  }, [currentSessions, focusedIndex, selectSession]);

  return (
    <div
      ref={sidebarRef}
      className="flex flex-col h-full bg-card/30"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      role="navigation"
      aria-label={t('title')}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-border bg-card/50">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-md bg-primary/10">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <h2 className="font-semibold">{t('title')}</h2>
        </div>
        {runningSessions > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-green-500/10 text-green-600 dark:text-green-400">
            <Activity className="h-3 w-3 animate-pulse" />
            <span className="text-xs font-medium">{runningSessions}</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as 'active' | 'archived' | 'history')}
        className="flex-1 flex flex-col min-h-0"
      >
        <div className="px-3 pt-3">
          <TabsList className="w-full grid grid-cols-3 h-9 p-1 bg-muted/50">
            <TabsTrigger value="active" className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm">
              {t('tabs.activeCount', { count: activeSessions.length })}
            </TabsTrigger>
            <TabsTrigger value="archived" className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm">
              {t('tabs.archivedCount', { count: archivedSessions.length })}
            </TabsTrigger>
            <TabsTrigger value="history" className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <History className="h-3 w-3 mr-1" />
              {t('tabs.history')}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="active" className="flex-1 mt-0 min-h-0">
          <ScrollArea className="h-full">
            <div className="p-3 space-y-2">
              {activeSessions.length === 0 ? (
                <EmptyState
                  title={t('empty.noSessions')}
                  hint={t('empty.noSessionsHint')}
                />
              ) : (
                activeSessions.map((session, index) => (
                  <SessionListItem
                    key={session.id}
                    session={session}
                    isFocused={activeTab === 'active' && focusedIndex === index}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="archived" className="flex-1 mt-0 min-h-0">
          <ScrollArea className="h-full">
            <div className="p-3 space-y-2">
              {archivedSessions.length === 0 ? (
                <EmptyState
                  title={t('empty.noArchivedSessions')}
                  hint={t('empty.noArchivedSessionsHint')}
                />
              ) : (
                archivedSessions.map((session, index) => (
                  <SessionListItem
                    key={session.id}
                    session={session}
                    isFocused={activeTab === 'archived' && focusedIndex === index}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="history" className="flex-1 mt-0 min-h-0 flex flex-col">
          {/* Search input */}
          <div className="px-3 pt-3 pb-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={historySearchText}
                onChange={(e) => setHistorySearchText(e.target.value)}
                placeholder={t('history.searchPlaceholder')}
                className="w-full h-8 pl-8 pr-3 text-xs rounded-md border border-border bg-background placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-3 pt-0 space-y-2">
              {isLoadingHistory ? (
                <div className="flex items-center justify-center py-12">
                  <span className="text-xs text-muted-foreground">{t('history.loading')}</span>
                </div>
              ) : historyEntries.length === 0 ? (
                <EmptyState
                  title={t('empty.noHistorySessions')}
                  hint={t('empty.noHistorySessionsHint')}
                />
              ) : (
                historyEntries.map((entry) => (
                  <HistoryListItem key={entry.id} entry={entry} />
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  hint: string;
}

function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="p-3 rounded-full bg-muted/50 mb-4">
        <Bot className="h-8 w-8 text-muted-foreground/40" />
      </div>
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <p className="text-xs text-muted-foreground/60 mt-1.5 max-w-[200px]">{hint}</p>
    </div>
  );
}

interface HistoryListItemProps {
  entry: SessionHistoryEntry;
}

function HistoryListItem({ entry }: HistoryListItemProps) {
  const { t } = useTranslation('agentSessions');

  const duration = entry.durationMs > 0
    ? formatDuration(entry.durationMs)
    : null;

  const completedDate = entry.completedAt
    ? new Date(entry.completedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : null;

  return (
    <div className={cn(
      'group flex flex-col gap-1 px-3 py-2.5 rounded-lg border border-border/50',
      'hover:bg-accent/50 hover:border-border transition-colors cursor-pointer',
      entry.success ? 'bg-card/50' : 'bg-destructive/5'
    )}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium truncate flex-1">{entry.title}</span>
        <span className={cn(
          'text-[10px] font-medium px-1.5 py-0.5 rounded-full shrink-0',
          entry.success
            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
            : 'bg-red-500/10 text-red-600 dark:text-red-400'
        )}>
          {entry.success ? t('status.completed') : t('status.failed')}
        </span>
      </div>
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        {completedDate && <span>{completedDate}</span>}
        {duration && (
          <>
            <span className="text-muted-foreground/40">·</span>
            <span>{duration}</span>
          </>
        )}
        <span className="text-muted-foreground/40">·</span>
        <span>{entry.subtaskCompleted}/{entry.subtaskTotal} {t('history.subtasks')}</span>
      </div>
    </div>
  );
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}
