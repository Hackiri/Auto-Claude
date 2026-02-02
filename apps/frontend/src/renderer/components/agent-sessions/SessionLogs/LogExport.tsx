import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Download } from 'lucide-react';
import { Button } from '../../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../ui/dropdown-menu';
import type { TaskLogEntry } from '../../../../shared/types/task';

interface LogExportProps {
  logs: TaskLogEntry[];
  sessionId: string;
}

function formatLogAsText(log: TaskLogEntry): string {
  const parts = [
    `[${log.timestamp}]`,
    `[${log.type.toUpperCase()}]`,
    log.phase ? `[${log.phase}]` : null,
    log.tool_name ? `(${log.tool_name})` : null,
    log.content,
  ];
  return parts.filter(Boolean).join(' ');
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function LogExport({ logs, sessionId }: LogExportProps) {
  const { t } = useTranslation('agentSessions');

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const baseFilename = `session-${sessionId}-logs-${timestamp}`;

  const handleExportJson = useCallback(() => {
    const data = JSON.stringify(logs, null, 2);
    downloadFile(data, `${baseFilename}.json`, 'application/json');
  }, [logs, baseFilename]);

  const handleExportText = useCallback(() => {
    const text = logs.map(formatLogAsText).join('\n');
    downloadFile(text, `${baseFilename}.txt`, 'text/plain');
  }, [logs, baseFilename]);

  if (logs.length === 0) {
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs gap-1 px-2"
        >
          <Download className="h-3 w-3" />
          {t('logFilter.export')}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handleExportJson}>
          {t('logFilter.exportJson')}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleExportText}>
          {t('logFilter.exportText')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
