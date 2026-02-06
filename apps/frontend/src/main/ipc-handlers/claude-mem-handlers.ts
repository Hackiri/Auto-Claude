/**
 * Claude-Mem Installation and Worker Management Handlers
 *
 * Handles IPC requests for checking claude-mem installation status,
 * installing the npm package, and starting the HTTP worker.
 */

import { ipcMain, type BrowserWindow } from 'electron';
import { spawn } from 'child_process';
import { IPC_CHANNELS } from '../../shared/constants/ipc';
import type { ClaudeMemStatus } from '../../shared/types/project';
import { appLog } from '../app-logger';
import { isWindows } from '../platform';

const DEFAULT_WORKER_URL = 'http://localhost:37777';

/**
 * Check if claude-mem is installed by running `npx claude-mem --version`.
 * Returns the version string if installed, or null if not.
 */
function checkInstalled(): Promise<string | null> {
  return new Promise((resolve) => {
    const command = isWindows() ? 'npx.cmd' : 'npx';
    const proc = spawn(command, ['claude-mem', '--version'], {
      timeout: 15000,
      shell: isWindows(),
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';

    proc.stdout.on('data', (data: Buffer) => {
      stdout += data.toString('utf-8');
    });

    proc.on('close', (code: number | null) => {
      if (code === 0 && stdout.trim()) {
        resolve(stdout.trim());
      } else {
        resolve(null);
      }
    });

    proc.on('error', () => {
      resolve(null);
    });
  });
}

/**
 * Check if the claude-mem worker is running by hitting the configured URL.
 */
async function checkWorkerHealth(url: string): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
    });

    clearTimeout(timeout);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Register claude-mem IPC handlers.
 */
export function registerClaudeMemHandlers(
  getMainWindow: () => BrowserWindow | null
): void {
  // Get installation and worker status
  ipcMain.handle(IPC_CHANNELS.CLAUDE_MEM_GET_STATUS, async (): Promise<{
    success: boolean;
    data?: ClaudeMemStatus;
    error?: string;
  }> => {
    try {
      const version = await checkInstalled();
      const installed = version !== null;

      let workerRunning = false;
      const workerUrl = DEFAULT_WORKER_URL;

      if (installed) {
        workerRunning = await checkWorkerHealth(workerUrl);
      }

      return {
        success: true,
        data: {
          installed,
          version: version || undefined,
          workerRunning,
          workerUrl,
        },
      };
    } catch (error) {
      appLog.error('Claude-mem status check error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Status check failed',
      };
    }
  });

  // Install claude-mem globally
  ipcMain.handle(IPC_CHANNELS.CLAUDE_MEM_INSTALL, async (): Promise<{
    success: boolean;
    error?: string;
  }> => {
    return new Promise((resolve) => {
      const command = isWindows() ? 'npm.cmd' : 'npm';
      const proc = spawn(command, ['install', '-g', 'claude-mem'], {
        shell: isWindows(),
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      const mainWindow = getMainWindow();

      proc.stdout.on('data', (data: Buffer) => {
        const text = data.toString('utf-8');
        mainWindow?.webContents.send(IPC_CHANNELS.CLAUDE_MEM_INSTALL_LOG, text);
      });

      proc.stderr.on('data', (data: Buffer) => {
        const text = data.toString('utf-8');
        mainWindow?.webContents.send(IPC_CHANNELS.CLAUDE_MEM_INSTALL_LOG, text);
      });

      proc.on('close', (code: number | null) => {
        if (code === 0) {
          appLog.info('claude-mem installed successfully');
          resolve({ success: true });
        } else {
          appLog.error(`claude-mem install failed with code ${code}`);
          resolve({
            success: false,
            error: `Installation failed with exit code ${code}`,
          });
        }
      });

      proc.on('error', (error: Error) => {
        appLog.error('claude-mem install spawn error:', error);
        resolve({
          success: false,
          error: error.message,
        });
      });
    });
  });

  // Start the claude-mem worker as a detached background process
  ipcMain.handle(IPC_CHANNELS.CLAUDE_MEM_START_WORKER, async (): Promise<{
    success: boolean;
    error?: string;
  }> => {
    try {
      const command = isWindows() ? 'npx.cmd' : 'npx';
      const proc = spawn(command, ['claude-mem', 'worker'], {
        detached: true,
        stdio: 'ignore',
        shell: isWindows(),
      });

      proc.unref();

      // Wait briefly then health-check
      await new Promise((r) => setTimeout(r, 2000));

      const running = await checkWorkerHealth(DEFAULT_WORKER_URL);

      if (running) {
        appLog.info('claude-mem worker started successfully');
        return { success: true };
      }

      return {
        success: false,
        error: 'Worker started but health check failed. It may still be initializing.',
      };
    } catch (error) {
      appLog.error('claude-mem worker start error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to start worker',
      };
    }
  });
}
