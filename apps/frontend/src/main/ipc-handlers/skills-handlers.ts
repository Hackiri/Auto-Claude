/**
 * Skills IPC Handlers
 *
 * Handles file operations for Claude Agent Skills generation and management.
 * All skills are stored in .claude/skills/[skill-name]/SKILL.md format.
 */

import { ipcMain } from 'electron';
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, statSync } from 'fs';
import { join } from 'path';
import matter from 'gray-matter';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, SkillContent, SkillExportResult, SkillReadResult, SkillsListResult, SkillGenerationOptions, SkillGenerationResult } from '../../shared/types';
import { generateSkillsFromProjectIndex } from '../../shared/utils/skillGenerator';

/**
 * Maximum skill file size to read (500KB)
 */
const MAX_SKILL_SIZE = 500 * 1024;

/**
 * Validates a skill name for safe file system operations.
 * Prevents directory traversal and ensures valid format.
 */
function validateSkillName(skillName: string): { valid: true } | { valid: false; error: string } {
  // Required
  if (!skillName || skillName.length === 0) {
    return { valid: false, error: 'Skill name is required' };
  }

  // Max length
  if (skillName.length > 64) {
    return { valid: false, error: 'Skill name must be 64 characters or less' };
  }

  // Valid characters: lowercase letters, numbers, hyphens only
  const namePattern = /^[a-z0-9-]+$/;
  if (!namePattern.test(skillName)) {
    return { valid: false, error: 'Skill name must contain only lowercase letters, numbers, and hyphens' };
  }

  // No directory traversal
  if (skillName.includes('..') || skillName.includes('/') || skillName.includes('\\')) {
    return { valid: false, error: 'Skill name contains invalid characters' };
  }

  // Reserved words
  const reservedWords = ['anthropic', 'claude'];
  if (reservedWords.some(word => skillName.includes(word))) {
    return { valid: false, error: 'Skill name cannot contain reserved words: anthropic, claude' };
  }

  return { valid: true };
}

/**
 * Get the skills directory path relative to project directory.
 * Creates the directory if it doesn't exist.
 */
function getSkillsDirectory(projectDir: string): string {
  const skillsDir = join(projectDir, '.claude', 'skills');

  // Create .claude/skills/ directory if it doesn't exist
  if (!existsSync(skillsDir)) {
    mkdirSync(skillsDir, { recursive: true });
  }

  return skillsDir;
}

/**
 * Register all skills-related IPC handlers
 */
export function registerSkillsHandlers(): void {
  // ============================================
  // Skills File Export
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_INSTALL,
    async (_, projectDir: string, skillName: string, skillDescription: string, skillInstructions: string): Promise<IPCResult<SkillExportResult>> => {
      try {
        // Validate skill name
        const validation = validateSkillName(skillName);
        if (!validation.valid) {
          return {
            success: false,
            error: validation.error
          };
        }

        // Get skills directory
        const skillsDir = getSkillsDirectory(projectDir);

        // Create skill subdirectory
        const skillDir = join(skillsDir, skillName);
        if (!existsSync(skillDir)) {
          mkdirSync(skillDir, { recursive: true });
        }

        // Generate SKILL.md content with YAML frontmatter using gray-matter
        const content = matter.stringify(skillInstructions, {
          name: skillName,
          description: skillDescription
        });

        // Write SKILL.md file
        const skillPath = join(skillDir, 'SKILL.md');
        writeFileSync(skillPath, content, 'utf-8');

        return {
          success: true,
          data: {
            success: true,
            path: skillPath
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to export skill'
        };
      }
    }
  );

  // ============================================
  // Skills File Read
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_GET,
    async (_, projectDir: string, skillName: string): Promise<IPCResult<SkillReadResult>> => {
      try {
        // Validate skill name
        const validation = validateSkillName(skillName);
        if (!validation.valid) {
          return {
            success: false,
            error: validation.error
          };
        }

        // Get skill file path
        const skillsDir = getSkillsDirectory(projectDir);
        const skillPath = join(skillsDir, skillName, 'SKILL.md');

        // Check if file exists
        if (!existsSync(skillPath)) {
          return {
            success: false,
            error: `Skill '${skillName}' not found`
          };
        }

        // Check file size
        const stats = statSync(skillPath);
        if (stats.size > MAX_SKILL_SIZE) {
          return {
            success: false,
            error: 'Skill file too large (max 500KB)'
          };
        }

        // Read and parse skill file
        const fileContent = readFileSync(skillPath, 'utf-8');
        const { data, content } = matter(fileContent);

        const skillContent: SkillContent = {
          metadata: {
            name: data.name || skillName,
            description: data.description || '',
            version: data.version,
            'disable-model-invocation': data['disable-model-invocation'],
            'allowed-tools': data['allowed-tools']
          },
          instructions: content
        };

        return {
          success: true,
          data: {
            success: true,
            content: skillContent
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to read skill'
        };
      }
    }
  );

  // ============================================
  // Skills List
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_LIST,
    async (_, projectDir: string): Promise<IPCResult<SkillsListResult>> => {
      try {
        // Get skills directory
        const skillsDir = getSkillsDirectory(projectDir);

        // List all skill directories
        const entries = readdirSync(skillsDir, { withFileTypes: true });

        const skillNames: string[] = [];
        for (const entry of entries) {
          if (entry.isDirectory()) {
            // Check if SKILL.md exists
            const skillPath = join(skillsDir, entry.name, 'SKILL.md');
            if (existsSync(skillPath)) {
              skillNames.push(entry.name);
            }
          }
        }

        // Sort alphabetically
        skillNames.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));

        return {
          success: true,
          data: {
            success: true,
            skills: skillNames
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to list skills'
        };
      }
    }
  );

  // ============================================
  // Skills Generation from Project Index
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_GENERATE,
    async (_, projectDir: string, options: SkillGenerationOptions = {}): Promise<IPCResult<SkillGenerationResult>> => {
      try {
        // Get project index path
        const projectIndexPath = join(projectDir, '.auto-claude', 'project_index.json');

        // Check if project index exists
        if (!existsSync(projectIndexPath)) {
          return {
            success: false,
            error: 'Project index not found. Run project analysis first.'
          };
        }

        // Read project index
        const projectIndexContent = readFileSync(projectIndexPath, 'utf-8');
        const projectIndex = JSON.parse(projectIndexContent);

        // Generate skills using the shared utility
        const result = generateSkillsFromProjectIndex(projectIndex, options);

        return {
          success: result.success,
          data: result
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to generate skills'
        };
      }
    }
  );
}
