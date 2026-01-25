import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, Radio, Terminal, Maximize2, Minimize2 } from 'lucide-react';
import { useSessionLogs } from '../../../hooks/useSessionLogs';
import { ScrollArea } from '../../ui/scroll-area';
import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '../../ui/collapsible';
import { cn } from '../../../lib/utils';

interface SessionLogViewerProps {
  sessionId: string;
}

export function SessionLogViewer({ sessionId }: SessionLogViewerProps) {
  const { t } = useTranslation('agentSessions');
  const { logs, isStreaming, logCount } = useSessionLogs(sessionId);
  const [isExpanded, setIsExpanded] = useState(true); // Default to expanded
  const [isMaximized, setIsMaximized] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isExpanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isExpanded]);

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
      {/* Header - always visible */}
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-accent/50 transition-colors bg-card/50"
        >
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-md bg-muted">
              <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <span className="font-medium text-sm">{t('logs.title')}</span>
            {logCount > 0 && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                {logCount}
              </Badge>
            )}
            {isStreaming && (
              <Badge variant="outline" className="text-[10px] px-2 py-0 h-5 text-green-600 border-green-600/30 bg-green-500/10">
                <Radio className="h-2.5 w-2.5 mr-1.5 animate-pulse" />
                {t('logs.streaming')}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </button>
      </CollapsibleTrigger>

      {/* Log content */}
      <CollapsibleContent>
        <div
          ref={scrollRef}
          className={cn(
            'overflow-y-auto bg-[#1a1a1a] font-mono text-xs border-t border-border',
            isMaximized ? 'h-96' : 'h-48'
          )}
        >
          {logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-6">
              <div className="p-2 rounded-lg bg-muted/20 mb-3">
                <Terminal className="h-6 w-6 text-muted-foreground/40" />
              </div>
              <p className="text-muted-foreground text-xs">{t('logs.noLogs')}</p>
              <p className="text-muted-foreground/50 text-[10px] mt-1">{t('logs.noLogsHint')}</p>
            </div>
          ) : (
            <div className="p-2">
              {logs.map((log, index) => (
                <LogEntry key={`${log.timestamp}-${index}`} log={log} />
              ))}
            </div>
          )}
        </div>

        {/* Footer with controls */}
        {logs.length > 0 && (
          <div className="flex items-center justify-between px-3 py-1.5 bg-muted/30 border-t border-border text-xs">
            <span className="text-muted-foreground">{logCount} entries</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs gap-1"
              onClick={() => setIsMaximized(!isMaximized)}
            >
              {isMaximized ? (
                <>
                  <Minimize2 className="h-3 w-3" />
                  Collapse
                </>
              ) : (
                <>
                  <Maximize2 className="h-3 w-3" />
                  Expand
                </>
              )}
            </Button>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}

interface LogEntryProps {
  log: {
    timestamp: string;
    type: string;
    content: string;
    phase?: string;
    tool_name?: string;
  };
}

function LogEntry({ log }: LogEntryProps) {
  const typeConfig = getLogTypeConfig(log.type);

  return (
    <div className={cn(
      'flex items-start gap-3 py-1 px-2 rounded hover:bg-white/5',
      typeConfig.bgClass
    )}>
      <span className="text-gray-500 flex-shrink-0 select-none tabular-nums">
        {formatTimestamp(log.timestamp)}
      </span>
      {log.tool_name && (
        <span className="text-blue-400 flex-shrink-0 font-medium">
          [{log.tool_name}]
        </span>
      )}
      <span className={cn('flex-1 break-all whitespace-pre-wrap', typeConfig.textClass)}>
        {log.content}
      </span>
    </div>
  );
}

function getLogTypeConfig(type: string) {
  switch (type) {
    case 'error':
      return {
        bgClass: 'bg-red-500/10',
        textClass: 'text-red-400'
      };
    case 'success':
      return {
        bgClass: 'bg-green-500/10',
        textClass: 'text-green-400'
      };
    case 'tool_start':
    case 'tool_end':
      return {
        bgClass: '',
        textClass: 'text-blue-400'
      };
    case 'phase_start':
    case 'phase_end':
      return {
        bgClass: 'bg-purple-500/10',
        textClass: 'text-purple-400 font-medium'
      };
    default:
      return {
        bgClass: '',
        textClass: 'text-gray-300'
      };
  }
}

function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return timestamp.slice(11, 19) || '--:--:--';
  }
}
