/**
 * Skills IPC Handlers
 *
 * Handles file operations for Claude Agent Skills generation and management.
 * All skills are stored in .claude/skills/[skill-name]/SKILL.md format.
 */

import { ipcMain } from 'electron';
import type { BrowserWindow } from 'electron';
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, statSync, appendFileSync } from 'fs';
import { join } from 'path';
import matter from 'gray-matter';
import { IPC_CHANNELS } from '../../shared/constants';

// Debug log file - writes to a persistent file for debugging
const DEBUG_LOG_PATH = '/tmp/skills-debug.log';
function debugToFile(message: string) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] ${message}\n`;
  try {
    appendFileSync(DEBUG_LOG_PATH, logLine);
  } catch (e) {
    console.error('Failed to write debug log:', e);
  }
}
import type { IPCResult, Skill, SkillContent, SkillExportResult, SkillReadResult, SkillsListResult, SkillGenerationOptions, SkillGenerationResult } from '../../shared/types';
import { generateSkillsFromProjectIndex } from '../../shared/utils/skillGenerator';
import { v4 as uuidv4 } from 'uuid';
import { projectStore } from '../project-store';
import type { AgentManager } from '../agent';
import type { SkillsConfig } from '../agent/types';
import { debugLog, debugError } from '../../shared/utils/debug-logger';
import { safeSendToRenderer } from './utils';

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
export function registerSkillsHandlers(
  agentManager: AgentManager,
  getMainWindow: () => BrowserWindow | null
): void {
  // STARTUP LOG - confirms handlers are registered
  debugToFile('========== SKILLS HANDLERS REGISTERED v6 ==========');
  console.log('[Skills Handlers] Registering IPC handlers v6');

  // ============================================
  // Skills File Export
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_INSTALL,
    async (_, projectIdOrPath: string, skillName: string, skillDescription: string, skillInstructions: string): Promise<IPCResult<SkillExportResult>> => {
      // ALWAYS log for debugging - not behind DEBUG flag
      // VERSION MARKER: 2024-01-24-v5 - If you don't see this, restart the app!
      debugToFile('========== SKILLS_INSTALL v5 ==========');
      debugToFile(`projectIdOrPath: ${projectIdOrPath}`);
      debugToFile(`skillName: ${skillName}`);
      debugToFile(`descriptionLength: ${skillDescription?.length}`);
      debugToFile(`instructionsLength: ${skillInstructions?.length}`);

      console.log('='.repeat(60));
      console.log('[SKILLS_INSTALL] VERSION: 2024-01-24-v5');
      console.log('[SKILLS_INSTALL] Request received');
      console.log('[SKILLS_INSTALL] projectIdOrPath:', projectIdOrPath);
      console.log('[SKILLS_INSTALL] skillName:', skillName);
      console.log('[SKILLS_INSTALL] descriptionLength:', skillDescription?.length);
      console.log('[SKILLS_INSTALL] instructionsLength:', skillInstructions?.length);

      // Log all projects in store for debugging
      const allProjects = projectStore.getProjects();
      debugToFile(`Projects in store: ${allProjects.length}`);
      console.log('[SKILLS_INSTALL] Projects in store:', allProjects.length);
      allProjects.forEach((p, i) => {
        debugToFile(`  Project ${i}: id=${p.id}, path=${p.path}`);
        console.log(`[SKILLS_INSTALL]   Project ${i}: id=${p.id}, path=${p.path}`);
      });
      console.log('='.repeat(60));

      try {
        // Validate skill name
        const validation = validateSkillName(skillName);
        if (!validation.valid) {
          console.error('[SKILLS_INSTALL] Invalid skill name:', validation.error);
          return {
            success: false,
            error: validation.error
          };
        }

        // Validate instructions
        if (!skillInstructions || skillInstructions.length === 0) {
          console.error('[SKILLS_INSTALL] Missing instructions for skill:', skillName);
          return {
            success: false,
            error: 'Skill instructions are required'
          };
        }

        // Resolve projectId to project path
        // First try to get project from store (if projectIdOrPath is an ID)
        let projectDir: string;
        const project = projectStore.getProject(projectIdOrPath);
        debugToFile(`projectStore.getProject result: ${project ? 'FOUND' : 'NOT FOUND'}`);
        console.log('[SKILLS_INSTALL] projectStore.getProject result:', project ? 'FOUND' : 'NOT FOUND');

        if (project) {
          projectDir = project.path;
          debugToFile(`Resolved project ID to path: ${projectDir}`);
          console.log('[SKILLS_INSTALL] Resolved project ID to path:', projectDir);
        } else if (projectIdOrPath.startsWith('/') || projectIdOrPath.includes(':\\')) {
          // It looks like an absolute path, use it directly
          projectDir = projectIdOrPath;
          debugToFile(`Using as absolute path: ${projectDir}`);
          console.log('[SKILLS_INSTALL] Using as absolute path:', projectDir);
        } else {
          // It's a UUID that wasn't found in the store - this is an error
          debugToFile(`ERROR: Project not found for ID: ${projectIdOrPath}`);
          console.error('[SKILLS_INSTALL] Project not found for ID:', projectIdOrPath);
          console.error('[SKILLS_INSTALL] This is the bug! ProjectId not in store.');
          return {
            success: false,
            error: `Project not found: ${projectIdOrPath}`
          };
        }

        // Get skills directory
        const skillsDir = getSkillsDirectory(projectDir);
        debugLog('[Skills Install] Skills directory:', skillsDir);

        // Create skill subdirectory
        const skillDir = join(skillsDir, skillName);
        if (!existsSync(skillDir)) {
          mkdirSync(skillDir, { recursive: true });
          debugLog('[Skills Install] Created skill directory:', skillDir);
        }

        // Generate SKILL.md content with YAML frontmatter using gray-matter
        const content = matter.stringify(skillInstructions, {
          name: skillName,
          description: skillDescription
        });

        // Write SKILL.md file
        const skillPath = join(skillDir, 'SKILL.md');
        writeFileSync(skillPath, content, 'utf-8');
        debugToFile(`SUCCESS: Wrote skill file to: ${skillPath}`);
        debugLog('[Skills Install] Wrote skill file:', skillPath);
        console.log('[SKILLS_INSTALL] SUCCESS: Wrote skill file to:', skillPath);

        return {
          success: true,
          data: {
            success: true,
            path: skillPath
          }
        };
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : 'Failed to export skill';
        debugToFile(`ERROR: ${errMsg}`);
        debugError('[Skills Install] Error:', error);
        console.error('[SKILLS_INSTALL] ERROR:', errMsg);
        return {
          success: false,
          error: errMsg
        };
      }
    }
  );

  // ============================================
  // Skills File Read
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_GET,
    async (_, projectIdOrPath: string, skillName: string): Promise<IPCResult<SkillReadResult>> => {
      try {
        // Validate skill name
        const validation = validateSkillName(skillName);
        if (!validation.valid) {
          return {
            success: false,
            error: validation.error
          };
        }

        // Resolve projectId to project path if needed
        let projectDir = projectIdOrPath;
        const project = projectStore.getProject(projectIdOrPath);
        if (project) {
          projectDir = project.path;
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
    async (_, projectIdOrPath: string): Promise<IPCResult<SkillsListResult>> => {
      // ALWAYS log for debugging
      debugToFile('========== SKILLS_LIST v6 ==========');
      debugToFile(`projectIdOrPath: ${projectIdOrPath}`);
      console.log('='.repeat(60));
      console.log('[SKILLS_LIST] Request for:', projectIdOrPath);

      try {
        // Resolve projectId to project path
        let projectDir: string;
        const project = projectStore.getProject(projectIdOrPath);
        console.log('[SKILLS_LIST] projectStore.getProject result:', project ? 'FOUND' : 'NOT FOUND');

        if (project) {
          projectDir = project.path;
          console.log('[SKILLS_LIST] Resolved project ID to path:', projectDir);
        } else if (projectIdOrPath.startsWith('/') || projectIdOrPath.includes(':\\')) {
          // It looks like an absolute path, use it directly
          projectDir = projectIdOrPath;
          console.log('[SKILLS_LIST] Using as absolute path:', projectDir);
        } else {
          // It's a UUID that wasn't found in the store - this is an error
          console.error('[SKILLS_LIST] Project not found for ID:', projectIdOrPath);
          return {
            success: false,
            error: `Project not found: ${projectIdOrPath}`
          };
        }

        // Get skills directory
        const skillsDir = getSkillsDirectory(projectDir);
        debugLog('[Skills List] Skills directory:', skillsDir);

        // List all skill directories
        const entries = readdirSync(skillsDir, { withFileTypes: true });

        const skillNames: string[] = [];
        for (const entry of entries) {
          if (entry.isDirectory()) {
            // Check if SKILL.md exists
            const skillPath = join(skillsDir, entry.name, 'SKILL.md');
            if (existsSync(skillPath)) {
              skillNames.push(entry.name);
              debugLog('[Skills List] Found skill:', entry.name);
            }
          }
        }

        // Sort alphabetically
        skillNames.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));

        debugLog('[Skills List] Found', skillNames.length, 'skills:', skillNames);
        debugToFile(`SKILLS_LIST found ${skillNames.length} skills: ${skillNames.join(', ')}`);

        return {
          success: true,
          data: {
            success: true,
            skills: skillNames
          }
        };
      } catch (error) {
        debugError('[Skills List] Error:', error);
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
    async (_, projectIdOrPath: string, options: SkillGenerationOptions = {}): Promise<IPCResult<SkillGenerationResult>> => {
      try {
        // Resolve projectId to project path if needed
        let projectDir = projectIdOrPath;
        const project = projectStore.getProject(projectIdOrPath);
        if (project) {
          projectDir = project.path;
        }

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

  // ============================================
  // Skills Generation from Natural Language Prompt
  // ============================================

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_GENERATE_FROM_PROMPT,
    async (_, projectDir: string, skillName: string, prompt: string): Promise<IPCResult<Skill>> => {
      debugToFile('========== SKILLS_GENERATE_FROM_PROMPT v5 ==========');
      debugToFile(`projectDir: ${projectDir}`);
      debugToFile(`skillName: ${skillName}`);
      debugToFile(`promptLength: ${prompt?.length}`);
      debugLog('[Skills Generate From Prompt] Request:', {
        projectDir,
        skillName,
        promptLength: prompt?.length
      });

      try {
        // Validate skill name
        const validation = validateSkillName(skillName);
        if (!validation.valid) {
          debugError('[Skills Generate From Prompt] Invalid skill name:', validation.error);
          return {
            success: false,
            error: validation.error
          };
        }

        // Validate prompt
        if (!prompt || prompt.trim().length < 10) {
          debugError('[Skills Generate From Prompt] Prompt too short');
          return {
            success: false,
            error: 'Prompt must be at least 10 characters long'
          };
        }

        if (prompt.length > 2000) {
          debugError('[Skills Generate From Prompt] Prompt too long');
          return {
            success: false,
            error: 'Prompt must be 2000 characters or less'
          };
        }

        // Generate skill instructions from the prompt
        // For now, create a structured skill based on the prompt
        // In the future, this could call an AI service to generate more sophisticated instructions
        const instructions = generateSkillInstructionsFromPrompt(skillName, prompt);
        debugLog('[Skills Generate From Prompt] Generated instructions length:', instructions.length);

        // Create the skill object
        const skill: Skill = {
          id: uuidv4(),
          name: skillName,
          description: extractDescriptionFromPrompt(prompt),
          enabled: true,
          source: 'service' as const, // Default source for prompt-generated skills
          metadata: {
            generatedFrom: 'prompt',
            prompt: prompt.substring(0, 500), // Store first 500 chars of prompt
            generatedAt: new Date().toISOString()
          },
          instructions
        };

        debugToFile(`Created skill: ${skill.name}, instructionsLength: ${skill.instructions.length}`);
        debugLog('[Skills Generate From Prompt] Created skill:', {
          id: skill.id,
          name: skill.name,
          descriptionLength: skill.description.length,
          instructionsLength: skill.instructions.length,
          hasInstructions: !!skill.instructions
        });

        // AUTO-SAVE: Save the skill directly in the main process
        // This ensures persistence regardless of what the renderer does
        try {
          // Resolve projectId to project path (projectDir is actually projectId from renderer)
          const projectIdOrPath = projectDir;
          let resolvedProjectDir: string;
          const project = projectStore.getProject(projectIdOrPath);

          if (project) {
            resolvedProjectDir = project.path;
            debugToFile(`Resolved projectId to path: ${resolvedProjectDir}`);
          } else if (projectIdOrPath.startsWith('/') || projectIdOrPath.includes(':\\')) {
            resolvedProjectDir = projectIdOrPath;
            debugToFile(`Using as absolute path: ${resolvedProjectDir}`);
          } else {
            debugToFile(`WARNING: Could not resolve projectId ${projectIdOrPath}, skipping auto-save`);
            // Still return the skill - renderer might be able to save it
            return {
              success: true,
              data: skill
            };
          }

          // Get skills directory and create if needed
          const skillsDir = getSkillsDirectory(resolvedProjectDir);
          const skillDir = join(skillsDir, skillName);
          if (!existsSync(skillDir)) {
            mkdirSync(skillDir, { recursive: true });
          }

          // Generate SKILL.md content with YAML frontmatter
          const content = matter.stringify(instructions, {
            name: skillName,
            description: skill.description
          });

          // Write SKILL.md file
          const skillPath = join(skillDir, 'SKILL.md');
          writeFileSync(skillPath, content, 'utf-8');
          debugToFile(`AUTO-SAVED skill to: ${skillPath}`);
          console.log('[SKILLS_GENERATE_FROM_PROMPT] AUTO-SAVED skill to:', skillPath);

        } catch (saveError) {
          // Log but don't fail - the skill was still generated
          const saveErrMsg = saveError instanceof Error ? saveError.message : 'Unknown save error';
          debugToFile(`AUTO-SAVE WARNING: ${saveErrMsg}`);
          console.warn('[SKILLS_GENERATE_FROM_PROMPT] Auto-save warning:', saveErrMsg);
        }

        debugToFile('SKILLS_GENERATE_FROM_PROMPT returning success');
        return {
          success: true,
          data: skill
        };
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : 'Failed to generate skill from prompt';
        debugToFile(`SKILLS_GENERATE_FROM_PROMPT ERROR: ${errMsg}`);
        debugError('[Skills Generate From Prompt] Error:', error);
        return {
          success: false,
          error: errMsg
        };
      }
    }
  );

  // ============================================
  // AI-Powered Skills Generation
  // ============================================

  ipcMain.on(
    IPC_CHANNELS.SKILLS_GENERATE_AI,
    (
      _,
      projectId: string,
      config?: SkillsConfig,
      refresh?: boolean
    ) => {
      debugLog('[Skills Handler] AI generation request:', {
        projectId,
        config,
        refresh
      });

      const mainWindow = getMainWindow();
      if (!mainWindow) return;

      const project = projectStore.getProject(projectId);
      if (!project) {
        debugError('[Skills Handler] Project not found:', projectId);
        safeSendToRenderer(
          getMainWindow,
          IPC_CHANNELS.SKILLS_GENERATE_AI_ERROR,
          projectId,
          'Project not found'
        );
        return;
      }

      // Note: No longer requiring project_index.json - AI will analyze project directly

      debugLog('[Skills Handler] Starting agent manager skills generation:', {
        projectId,
        projectPath: project.path,
        config
      });

      // Start skills generation via agent manager
      agentManager.startSkillsGeneration(
        projectId,
        project.path,
        config || {},
        refresh ?? false
      );

      // Send initial progress
      safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_PROGRESS, projectId, {
        phase: 'analyzing',
        progress: 10,
        message: 'Analyzing project architecture...'
      });
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.SKILLS_GENERATE_AI_STOP,
    async (_, projectId: string): Promise<IPCResult> => {
      debugLog('[Skills Handler] Stop AI generation request:', { projectId });

      const wasStopped = agentManager.stopSkillsGeneration(projectId);

      debugLog('[Skills Handler] Stop result:', { projectId, wasStopped });

      if (wasStopped) {
        safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_STOPPED, projectId);
      }

      return { success: wasStopped };
    }
  );

  // ============================================
  // Register AI Skills Generation Event Listeners
  // ============================================

  // Forward progress events from agent manager to renderer
  agentManager.on('skills-progress', (projectId: string, status: { phase: string; progress: number; message: string }) => {
    safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_PROGRESS, projectId, status);
  });

  // Forward log events for debugging
  agentManager.on('skills-log', (projectId: string, log: string) => {
    debugLog('[Skills] Log:', { projectId, log });
  });

  // Forward completion events with generated skills
  agentManager.on('skills-complete', (projectId: string, skills: Array<{ name: string; description: string; instructions: string }>) => {
    debugLog('[Skills] Generation complete:', { projectId, skillsCount: skills.length });
    safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_COMPLETE, projectId, skills);
  });

  // Forward error events
  agentManager.on('skills-error', (projectId: string, error: string) => {
    debugError('[Skills] Generation error:', { projectId, error });
    safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_ERROR, projectId, error);
  });

  // Forward stopped events
  agentManager.on('skills-stopped', (projectId: string) => {
    debugLog('[Skills] Generation stopped:', { projectId });
    safeSendToRenderer(getMainWindow, IPC_CHANNELS.SKILLS_GENERATE_AI_STOPPED, projectId);
  });
}

/**
 * Generate skill instructions from a natural language prompt
 */
function generateSkillInstructionsFromPrompt(skillName: string, prompt: string): string {
  // Create a structured skill document from the user's prompt
  const instructions = `# ${skillName}

## Overview

${prompt}

## When to Use This Skill

Use this skill when working on tasks that involve:
- Tasks matching the description above
- Related patterns and implementations in this codebase

## Guidelines

When applying this skill, Claude should:

1. **Understand the Context**: Review relevant files and existing patterns before making changes
2. **Follow Conventions**: Match the existing code style and patterns in the project
3. **Implement Carefully**: Make incremental changes and verify each step
4. **Test Thoroughly**: Ensure changes work correctly and don't break existing functionality

## Best Practices

- Always read existing code before making modifications
- Use the project's established patterns and conventions
- Write clear, maintainable code with appropriate comments
- Consider edge cases and error handling
- Follow the principle of least surprise

## Notes

This skill was generated from a user prompt. Consider customizing the instructions above to better match your specific needs and project requirements.
`;

  return instructions;
}

/**
 * Extract a concise description from the prompt (first 150 chars)
 */
function extractDescriptionFromPrompt(prompt: string): string {
  // Clean up the prompt and extract a description
  const cleaned = prompt.trim().replace(/\s+/g, ' ');

  if (cleaned.length <= 150) {
    return cleaned;
  }

  // Find a good breaking point (end of sentence or word)
  const truncated = cleaned.substring(0, 150);
  const lastPeriod = truncated.lastIndexOf('.');
  const lastSpace = truncated.lastIndexOf(' ');

  if (lastPeriod > 100) {
    return truncated.substring(0, lastPeriod + 1);
  }

  if (lastSpace > 100) {
    return truncated.substring(0, lastSpace) + '...';
  }

  return truncated + '...';
}
