import { useTranslation } from 'react-i18next';
import { Bot, } from 'lucide-react';
import { useSessionProgress } from '../../../hooks/useSessionProgress';
import { SessionHeader } from './SessionHeader';
import { SessionKanban } from './SessionKanban';
import { SessionLogViewer } from '../SessionLogs/SessionLogViewer';

interface SessionDetailProps {
  sessionId: string | null;
}

export function SessionDetail({ sessionId }: SessionDetailProps) {
  const { t } = useTranslation('agentSessions');
  const { session, tasks, taskStats } = useSessionProgress(sessionId);

  if (!session) {
    return <EmptySessionState />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <SessionHeader session={session} taskStats={taskStats} />

      {/* Main content - Kanban and Logs */}
      <div className="flex-1 min-h-0 flex flex-col">
        {/* Kanban Board */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <SessionKanban sessionId={session.id} tasks={tasks} />
        </div>

        {/* Log Viewer - collapsible at the bottom */}
        <div className="border-t border-border">
          <SessionLogViewer sessionId={session.id} />
        </div>
      </div>
    </div>
  );
}

function EmptySessionState() {
  const { t } = useTranslation('agentSessions');

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Bot className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium text-foreground mb-2">
        {t('detail.noSelection')}
      </h3>
      <p className="text-sm text-muted-foreground max-w-md">
        {t('detail.noSelectionHint')}
      </p>
    </div>
  );
}
