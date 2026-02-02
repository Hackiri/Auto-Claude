import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync } from 'fs';
import path from 'path';
import type { SessionHistoryEntry } from '../../shared/types';
import { SessionHistoryPaths } from './session-history-paths';

/**
 * Session history storage manager
 * Handles persisting and loading agent session history from the filesystem
 */
export class SessionHistoryStorage {
  private paths: SessionHistoryPaths;

  constructor(paths: SessionHistoryPaths) {
    this.paths = paths;
  }

  /**
   * Load a specific session history entry from disk
   */
  loadSessionById(projectPath: string, sessionId: string): SessionHistoryEntry | null {
    const sessionPath = this.paths.getSessionPath(projectPath, sessionId);
    if (!existsSync(sessionPath)) return null;

    try {
      const content = readFileSync(sessionPath, 'utf-8');
      return JSON.parse(content) as SessionHistoryEntry;
    } catch {
      return null;
    }
  }

  /**
   * Save session history entry to disk
   */
  saveSession(projectPath: string, entry: SessionHistoryEntry): void {
    const historyDir = this.paths.getHistoryDir(projectPath);
    if (!existsSync(historyDir)) {
      mkdirSync(historyDir, { recursive: true });
    }

    const sessionPath = this.paths.getSessionPath(projectPath, entry.id);
    writeFileSync(sessionPath, JSON.stringify(entry, null, 2), 'utf-8');
  }

  /**
   * Delete a session history entry from disk
   */
  deleteSession(projectPath: string, sessionId: string): boolean {
    const sessionPath = this.paths.getSessionPath(projectPath, sessionId);
    if (!existsSync(sessionPath)) return false;

    try {
      unlinkSync(sessionPath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * List all session history entries for a project
   */
  listSessions(projectPath: string): SessionHistoryEntry[] {
    const historyDir = this.paths.getHistoryDir(projectPath);
    if (!existsSync(historyDir)) return [];

    try {
      const files = readdirSync(historyDir).filter(f => f.endsWith('.json'));
      const entries: SessionHistoryEntry[] = [];

      for (const file of files) {
        try {
          const content = readFileSync(path.join(historyDir, file), 'utf-8');
          const entry = JSON.parse(content) as SessionHistoryEntry;
          entries.push(entry);
        } catch {
          // Skip invalid session files
        }
      }

      // Sort by updatedAt descending (most recent first)
      return entries.sort((a, b) =>
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      );
    } catch {
      return [];
    }
  }
}
