import path from 'path';

const AGENT_SESSIONS_DIR = '.auto-claude/agent-sessions';
const HISTORY_DIR = 'history';

/**
 * Path utilities for agent session history storage
 * Provides consistent path resolution for session history data
 */
export class SessionHistoryPaths {
  /**
   * Get agent sessions directory path for a project
   */
  getAgentSessionsDir(projectPath: string): string {
    return path.join(projectPath, AGENT_SESSIONS_DIR);
  }

  /**
   * Get history directory path for a project
   */
  getHistoryDir(projectPath: string): string {
    return path.join(this.getAgentSessionsDir(projectPath), HISTORY_DIR);
  }

  /**
   * Get session history file path for a specific session
   */
  getSessionPath(projectPath: string, sessionId: string): string {
    return path.join(this.getHistoryDir(projectPath), `${sessionId}.json`);
  }
}
