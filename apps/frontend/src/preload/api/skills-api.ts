import { ipcRenderer } from 'electron';
import matter from 'gray-matter';
import { IPC_CHANNELS } from '../../shared/constants';
import type {
  IPCResult,
  Skill,
  SkillGenerationOptions,
  SkillGenerationResult,
  SkillExportResult,
} from '../../shared/types';

export interface SkillsAPI {
  /**
   * Generate skills from project index
   */
  generateSkills: (
    projectId: string,
    options?: SkillGenerationOptions
  ) => Promise<IPCResult<SkillGenerationResult>>;

  /**
   * Load existing skills from .claude/skills/ directory
   */
  loadSkills: (projectId: string) => Promise<IPCResult<string[]>>;

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
}

export const createSkillsAPI = (): SkillsAPI => ({
  generateSkills: (projectId, options = {}) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_GENERATE, projectId, options),

  loadSkills: (projectId) =>
    ipcRenderer.invoke(IPC_CHANNELS.SKILLS_LIST, projectId),

  exportSkills: async (projectId, skills) => {
    try {
      // Export each skill individually
      for (const skill of skills) {
        // Generate SKILL.md content with YAML frontmatter using gray-matter
        const content = matter.stringify(skill.instructions, {
          name: skill.name,
          description: skill.description
        });

        const result = await ipcRenderer.invoke(
          IPC_CHANNELS.SKILLS_INSTALL,
          projectId,
          skill.name,
          content
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
      // Generate SKILL.md content with YAML frontmatter using gray-matter
      const content = matter.stringify(skill.instructions, {
        name: skill.name,
        description: skill.description
      });

      return ipcRenderer.invoke(
        IPC_CHANNELS.SKILLS_INSTALL,
        projectId,
        skill.name,
        content
      );
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to export skill'
      };
    }
  }
});
