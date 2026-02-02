import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { GitCompareArrows, X } from 'lucide-react';
import { useAgentSessionsStore, syncSessionsFromTasks } from '../../stores/agent-sessions-store';
import { useTaskStore } from '../../stores/task-store';
import { useProjectStore } from '../../stores/project-store';
import { SessionSidebar } from './SessionSidebar/SessionSidebar';
import { SessionDetail } from './SessionDetail/SessionDetail';
import { SessionComparison } from './SessionComparison/SessionComparison';
import { AnalyticsDashboard } from './Analytics';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';

export function AgentSessions() {
  const { t } = useTranslation('agentSessions');
  const tasks = useTaskStore((state) => state.tasks);
  const selectedSessionId = useAgentSessionsStore((state) => state.selectedSessionId);
  const comparisonSessionIds = useAgentSessionsStore((state) => state.comparisonSessionIds);
  const selectSession = useAgentSessionsStore((state) => state.selectSession);
  const clearComparison = useAgentSessionsStore((state) => state.clearComparison);
  const activeProjectId = useProjectStore((state) => state.activeProjectId);
  const selectedProjectId = useProjectStore((state) => state.selectedProjectId);
  const [activeTab, setActiveTab] = useState<string>('sessions');

  // Sync sessions from tasks whenever tasks change
  useEffect(() => {
    syncSessionsFromTasks(tasks);
  }, [tasks]);

  // Clear session selection and comparison when project changes
  useEffect(() => {
    selectSession(null);
    clearComparison();
  }, [activeProjectId, selectedProjectId, selectSession, clearComparison]);

  const isComparing = comparisonSessionIds !== null;

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
      <div className="flex-shrink-0 border-b border-border px-4 pt-2">
        <TabsList>
          <TabsTrigger value="sessions">{t('tabs.sessions')}</TabsTrigger>
          <TabsTrigger value="analytics">{t('tabs.analytics')}</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="sessions" className="flex-1 min-h-0 mt-0">
        <div className="flex h-full">
          {/* Left panel: Session list */}
          <div className="w-80 border-r border-border flex-shrink-0">
            <SessionSidebar />
          </div>

          {/* Right panel: Session detail or comparison */}
          <div className="flex-1 min-w-0">
            {isComparing ? (
              <div className="flex flex-col h-full">
                {/* Comparison header with exit button */}
                <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <GitCompareArrows className="h-4 w-4" />
                    <span>{t('comparison.title')}</span>
                  </div>
                  <button
                    onClick={clearComparison}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-md hover:bg-muted"
                  >
                    <X className="h-3.5 w-3.5" />
                    {t('comparison.exitComparison')}
                  </button>
                </div>
                <div className="flex-1 min-h-0">
                  <SessionComparison sessionIds={comparisonSessionIds} />
                </div>
              </div>
            ) : (
              <SessionDetail sessionId={selectedSessionId} />
            )}
          </div>
        </div>
      </TabsContent>

      <TabsContent value="analytics" className="flex-1 min-h-0 mt-0">
        <AnalyticsDashboard />
      </TabsContent>
    </Tabs>
  );
}
