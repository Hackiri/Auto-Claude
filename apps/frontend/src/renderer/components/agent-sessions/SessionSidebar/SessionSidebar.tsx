import { useTranslation } from 'react-i18next';
import { Bot, Activity } from 'lucide-react';
import { ScrollArea } from '../../ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../ui/tabs';
import { useAgentSessionsStore } from '../../../stores/agent-sessions-store';
import { SessionListItem } from './SessionListItem';
import { cn } from '../../../lib/utils';

export function SessionSidebar() {
  const { t } = useTranslation('agentSessions');
  const sessions = useAgentSessionsStore((state) => state.sessions);
  const activeTab = useAgentSessionsStore((state) => state.activeTab);
  const setActiveTab = useAgentSessionsStore((state) => state.setActiveTab);
  const getActiveSessions = useAgentSessionsStore((state) => state.getActiveSessions);
  const getArchivedSessions = useAgentSessionsStore((state) => state.getArchivedSessions);

  const activeSessions = getActiveSessions();
  const archivedSessions = getArchivedSessions();

  // Count running sessions
  const runningSessions = activeSessions.filter(s => s.status === 'running').length;

  return (
    <div className="flex flex-col h-full bg-card/30">
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
        onValueChange={(value) => setActiveTab(value as 'active' | 'archived')}
        className="flex-1 flex flex-col min-h-0"
      >
        <div className="px-3 pt-3">
          <TabsList className="w-full grid grid-cols-2 h-9 p-1 bg-muted/50">
            <TabsTrigger value="active" className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm">
              {t('tabs.activeCount', { count: activeSessions.length })}
            </TabsTrigger>
            <TabsTrigger value="archived" className="text-xs data-[state=active]:bg-background data-[state=active]:shadow-sm">
              {t('tabs.archivedCount', { count: archivedSessions.length })}
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
                activeSessions.map((session) => (
                  <SessionListItem key={session.id} session={session} />
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
                archivedSessions.map((session) => (
                  <SessionListItem key={session.id} session={session} />
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
