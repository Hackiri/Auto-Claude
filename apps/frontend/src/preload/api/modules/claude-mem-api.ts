/**
 * Claude-Mem API
 *
 * Exposes claude-mem installation and worker management functionality to the renderer.
 */

import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants/ipc';
import type { IPCResult } from '../../../shared/types/common';
import type { ClaudeMemStatus } from '../../../shared/types/project';

export interface ClaudeMemAPI {
  /** Check claude-mem installation and worker status */
  getClaudeMemStatus: () => Promise<IPCResult<ClaudeMemStatus>>;
  /** Install claude-mem globally via npm */
  installClaudeMem: () => Promise<IPCResult>;
  /** Start the claude-mem HTTP worker */
  startClaudeMemWorker: () => Promise<IPCResult>;
  /** Listen for installation log output */
  onClaudeMemInstallLog: (callback: (data: string) => void) => () => void;
}

export function createClaudeMemAPI(): ClaudeMemAPI {
  return {
    getClaudeMemStatus: () =>
      ipcRenderer.invoke(IPC_CHANNELS.CLAUDE_MEM_GET_STATUS),

    installClaudeMem: () =>
      ipcRenderer.invoke(IPC_CHANNELS.CLAUDE_MEM_INSTALL),

    startClaudeMemWorker: () =>
      ipcRenderer.invoke(IPC_CHANNELS.CLAUDE_MEM_START_WORKER),

    onClaudeMemInstallLog: (callback: (data: string) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, data: string) => callback(data);
      ipcRenderer.on(IPC_CHANNELS.CLAUDE_MEM_INSTALL_LOG, handler);
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.CLAUDE_MEM_INSTALL_LOG, handler);
      };
    },
  };
}
