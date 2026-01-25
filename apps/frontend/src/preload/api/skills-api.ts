import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type {
  IPCResult,
  Skill,
  SkillGenerationOptions,
  SkillGenerationResult,
  SkillExportResult,
  SkillReadResult,
} from '../../shared/types';

/**
 * Configuration for AI-powered skills generation
 */
export interface SkillsAIConfig {
  model?: string;          // Model shorthand (opus, sonnet, haiku)
  thinkingLevel?: string;  // Thinking level (none, low, medium, high, ultrathink)
  maxSkills?: number;      // Maximum number of skills to generate (default: 8)
}

/**
 * Progress data for AI skills generation
 */
export interface SkillsProgressData {
  phase: string;
  progress: number;
  message: string;
}

/**
 * AI-generated skill data
 */
export interface GeneratedSkill {
  name: string;
  description: string;
  instructions: string;
}

export interface SkillsAPI {
  /**
   * Generate skills from project index (template-based)
   */
  generateSkills: (
    projectId: string,
    options?: SkillGenerationOptions
  ) => Promise<IPCResult<SkillGenerationResult>>;

  /**
   * Generate a single skill from a natural language prompt
   */
  generateSkillFromPrompt: (
    projectId: string,
    skillName: string,
    prompt: string
  ) => Promise<IPCResult<Skill>>;

  /**
   * Load existing skills from .claude/skills/ directory (returns skill names)
   */
  loadSkills: (projectId: string) => Promise<IPCResult<{ success: boolean; skills?: string[] }>>;

  /**
   * Get a single skill's full content by name
   */
  getSkill: (projectId: string, skillName: string) => Promise<IPCResult<SkillReadResult>>;

  /**
   * Export multiple skills to .claude/skills/ directory
   */
  exportSkills: (
    projectId: string,
    skills: Skill[]
  ) => Promise<IPCResult<void>>;

  /**
   * Export a single skill to .claude/skills/ directory
   */
  exportSkill: (
    projectId: string,
    skill: Skill
  ) => Promise<IPCResult<SkillExportResult>>;

  // ============================================
  // AI-Powered Skills Generation
  // ============================================

  /**
   * Start AI-powered skills generation
   * Results are delivered via events (onSkillsAIProgress, onSkillsAIComplete, onSkillsAIError)
   */
  generateSkillsAI: (
    projectId: string,
    config?: SkillsAIConfig,
    refresh?: boolean
  ) => void;

  /**
   * Stop AI skills generation
   */
  stopSkillsAI: (projectId: string) => Promise<IPCResult>;

  /**
   * Listen for AI skills generation progress updates
   */
  onSkillsAIProgress: (
    callback: (projectId: string, status: SkillsProgressData) => void
  ) => () => void;

  /**
   * Listen for AI skills generation completion
   */
  onSkillsAIComplete: (
    callback: (projectId: string, skills: GeneratedSkill[]) => void
  ) => () => void;

  /**
   * Listen for AI skills generation errors
   */
  onSkillsAIError: (
    callback: (projectId: string, error: string) => void
  ) => () => void;

  /**
   * Listen for AI skills generation stopped
   */
  onSkillsAIStopped: (
    callback: (projectId: string) => void
  ) => () => void;
}

export const createSkillsAPI = (): SkillsAPI => ({
  generateSkills: (projectId, options = {}) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_GENERATE, projectId, options),

  generateSkillFromPrompt: (projectId, skillName, prompt) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_GENERATE_FROM_PROMPT, projectId, skillName, prompt),

  loadSkills: (projectId) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_LIST, projectId),

  getSkill: (projectId, skillName) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_GET, projectId, skillName),

  exportSkills: async (projectId, skills) => {
    try {
      // Export each skill individually - main process handles YAML frontmatter generation
      for (const skill of skills) {
        const result = await ipcRenderer.invoke(
          IPC_CHANNELS.SKILLS_INSTALL,
          projectId,
          skill.name,
          skill.description,
          skill.instructions
        );

        if (!result.success) {
          return {
            success: false,
            error: `Failed to export skill ${skill.name}: ${result.error}`
          };
        }
      }

      return { success: true, data: undefined };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  exportSkill: async (projectId, skill) => {
    try {
      // Main process handles YAML frontmatter generation with gray-matter
      return ipcRenderer.invoke(
        IPC_CHANNELS.SKILLS_INSTALL,
        projectId,
        skill.name,
        skill.description,
        skill.instructions
      );
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to export skill'
      };
    }
  },

  // ============================================
  // AI-Powered Skills Generation
  // ============================================

  generateSkillsAI: (projectId, config, refresh) => {
    ipcRenderer.send(IPC_CHANNELS.SKILLS_GENERATE_AI, projectId, config, refresh);
  },

  stopSkillsAI: (projectId) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_GENERATE_AI_STOP, projectId),

  onSkillsAIProgress: (callback) => {
    const handler = (_: Electron.IpcRendererEvent, projectId: string, status: SkillsProgressData) => {
      callback(projectId, status);
    };
    ipcRenderer.on(IPC_CHANNELS.SKILLS_GENERATE_AI_PROGRESS, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.SKILLS_GENERATE_AI_PROGRESS, handler);
    };
  },

  onSkillsAIComplete: (callback) => {
    const handler = (_: Electron.IpcRendererEvent, projectId: string, skills: GeneratedSkill[]) => {
      callback(projectId, skills);
    };
    ipcRenderer.on(IPC_CHANNELS.SKILLS_GENERATE_AI_COMPLETE, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.SKILLS_GENERATE_AI_COMPLETE, handler);
    };
  },

  onSkillsAIError: (callback) => {
    const handler = (_: Electron.IpcRendererEvent, projectId: string, error: string) => {
      callback(projectId, error);
    };
    ipcRenderer.on(IPC_CHANNELS.SKILLS_GENERATE_AI_ERROR, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.SKILLS_GENERATE_AI_ERROR, handler);
    };
  },

  onSkillsAIStopped: (callback) => {
    const handler = (_: Electron.IpcRendererEvent, projectId: string) => {
      callback(projectId);
    };
    ipcRenderer.on(IPC_CHANNELS.SKILLS_GENERATE_AI_STOPPED, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.SKILLS_GENERATE_AI_STOPPED, handler);
    };
  }
});
