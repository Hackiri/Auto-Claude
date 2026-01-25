import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAgentSessionsStore, syncSessionsFromTasks } from '../../stores/agent-sessions-store';
import { useTaskStore } from '../../stores/task-store';
import { useProjectStore } from '../../stores/project-store';
import { SessionSidebar } from './SessionSidebar/SessionSidebar';
import { SessionDetail } from './SessionDetail/SessionDetail';
import { cn } from '../../lib/utils';

export function AgentSessions() {
  const { t } = useTranslation('agentSessions');
  const tasks = useTaskStore((state) => state.tasks);
  const selectedSessionId = useAgentSessionsStore((state) => state.selectedSessionId);
  const selectSession = useAgentSessionsStore((state) => state.selectSession);
  const activeProjectId = useProjectStore((state) => state.activeProjectId);
  const selectedProjectId = useProjectStore((state) => state.selectedProjectId);

  // Sync sessions from tasks whenever tasks change
  useEffect(() => {
    syncSessionsFromTasks(tasks);
  }, [tasks]);

  // Clear session selection when project changes
  useEffect(() => {
    selectSession(null);
  }, [activeProjectId, selectedProjectId, selectSession]);

  return (
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
  );
}
