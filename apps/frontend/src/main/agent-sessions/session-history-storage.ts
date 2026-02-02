import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync, unlinkSync, statSync } from 'fs';
import path from 'path';
import type { SessionHistoryEntry } from '../../shared/types';
import { SessionHistoryPaths } from './session-history-paths';

/** Maximum number of session files to retain per project */
const MAX_SESSIONS = 500;

/** Default max age in milliseconds (90 days) */
const DEFAULT_MAX_AGE_MS = 90 * 24 * 60 * 60 * 1000;

/**
 * Validate that a parsed object has the required SessionHistoryEntry shape.
 * Returns true if the entry has all required fields with correct types.
 */
function isValidSessionEntry(obj: unknown): obj is SessionHistoryEntry {
  if (obj === null || typeof obj !== 'object') return false;
  const entry = obj as Record<string, unknown>;
  return (
    typeof entry.id === 'string' &&
    typeof entry.specId === 'string' &&
    typeof entry.projectId === 'string' &&
    typeof entry.title === 'string' &&
    typeof entry.status === 'string' &&
    typeof entry.success === 'boolean' &&
    typeof entry.createdAt === 'string' &&
    typeof entry.durationMs === 'number' &&
    typeof entry.updatedAt === 'string' &&
    Array.isArray(entry.phaseDurations)
  );
}

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
   * Load a specific session history entry from disk.
   * Skips corrupted or invalid JSON files gracefully.
   */
  loadSessionById(projectPath: string, sessionId: string): SessionHistoryEntry | null {
    const sessionPath = this.paths.getSessionPath(projectPath, sessionId);
    if (!existsSync(sessionPath)) return null;

    try {
      const content = readFileSync(sessionPath, 'utf-8');
      const parsed: unknown = JSON.parse(content);
      if (!isValidSessionEntry(parsed)) return null;
      return parsed;
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
   * List all session history entries for a project.
   * Corrupted or invalid JSON files are silently skipped.
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
          const parsed: unknown = JSON.parse(content);
          if (isValidSessionEntry(parsed)) {
            entries.push(parsed);
          }
          // Invalid shape is silently skipped (corrupted file recovery)
        } catch {
          // Skip unparseable files
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

  /**
   * Clean up old session files that exceed the max age or count limit.
   * Removes corrupted files unconditionally.
   * Returns the number of files removed.
   */
  cleanupOldSessions(projectPath: string, maxAgeMs: number = DEFAULT_MAX_AGE_MS): number {
    const historyDir = this.paths.getHistoryDir(projectPath);
    if (!existsSync(historyDir)) return 0;

    let removed = 0;
    const now = Date.now();

    try {
      const files = readdirSync(historyDir).filter(f => f.endsWith('.json'));

      // First pass: remove corrupted files and collect valid entries with metadata
      const validFiles: { file: string; updatedAt: number }[] = [];

      for (const file of files) {
        const filePath = path.join(historyDir, file);
        try {
          const content = readFileSync(filePath, 'utf-8');
          const parsed: unknown = JSON.parse(content);

          if (!isValidSessionEntry(parsed)) {
            // Remove corrupted/invalid files
            unlinkSync(filePath);
            removed++;
            continue;
          }

          const updatedAt = new Date(parsed.updatedAt).getTime();

          // Remove entries older than max age
          if (now - updatedAt > maxAgeMs) {
            unlinkSync(filePath);
            removed++;
            continue;
          }

          validFiles.push({ file, updatedAt });
        } catch {
          // Unparseable file - remove it
          try {
            unlinkSync(filePath);
            removed++;
          } catch {
            // Ignore deletion failures
          }
        }
      }

      // Second pass: enforce count limit (keep newest)
      if (validFiles.length > MAX_SESSIONS) {
        validFiles.sort((a, b) => b.updatedAt - a.updatedAt);
        const toRemove = validFiles.slice(MAX_SESSIONS);

        for (const { file } of toRemove) {
          try {
            unlinkSync(path.join(historyDir, file));
            removed++;
          } catch {
            // Ignore deletion failures
          }
        }
      }
    } catch {
      // Directory read failure - nothing to clean
    }

    return removed;
  }
}
