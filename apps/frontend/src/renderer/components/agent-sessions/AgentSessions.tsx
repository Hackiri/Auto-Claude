import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAgentSessionsStore, syncSessionsFromTasks } from '../../stores/agent-sessions-store';
import { useTaskStore } from '../../stores/task-store';
import { useProjectStore } from '../../stores/project-store';
import { SessionSidebar } from './SessionSidebar/SessionSidebar';
import { SessionDetail } from './SessionDetail/SessionDetail';
import { AnalyticsDashboard } from './Analytics';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../ui/tabs';

export function AgentSessions() {
  const { t } = useTranslation('agentSessions');
  const tasks = useTaskStore((state) => state.tasks);
  const selectedSessionId = useAgentSessionsStore((state) => state.selectedSessionId);
  const selectSession = useAgentSessionsStore((state) => state.selectSession);
  const activeProjectId = useProjectStore((state) => state.activeProjectId);
  const selectedProjectId = useProjectStore((state) => state.selectedProjectId);
  const [activeTab, setActiveTab] = useState<string>('sessions');

  // Sync sessions from tasks whenever tasks change
  useEffect(() => {
    syncSessionsFromTasks(tasks);
  }, [tasks]);

  // Clear session selection when project changes
  useEffect(() => {
    selectSession(null);
  }, [activeProjectId, selectedProjectId, selectSession]);

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

          {/* Right panel: Session detail */}
          <div className="flex-1 min-w-0">
            <SessionDetail sessionId={selectedSessionId} />
          </div>
        </div>
      </TabsContent>

      <TabsContent value="analytics" className="flex-1 min-h-0 mt-0">
        <AnalyticsDashboard />
      </TabsContent>
    </Tabs>
  );
}
