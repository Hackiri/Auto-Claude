/**
 * Skill-related types for Claude Agent Skills generation and management
 */

// ============================================
// Core Skill Types
// ============================================

/**
 * Skill source types derived from project index
 */
export type SkillSource = 'service' | 'database' | 'api' | 'ci';

/**
 * YAML frontmatter metadata for SKILL.md files
 */
export interface SkillMetadata {
  name: string;
  description: string;
  version?: string;
  'disable-model-invocation'?: boolean;
  'allowed-tools'?: string[];
}

/**
 * Main skill object representing an auto-generated or edited skill
 */
export interface Skill {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  source: SkillSource;
  metadata: Record<string, unknown>;
  /** Markdown instructions body */
  instructions: string;
}

/**
 * Parsed SKILL.md file content
 */
export interface SkillContent {
  /** YAML frontmatter metadata */
  metadata: SkillMetadata;
  /** Markdown instructions body */
  instructions: string;
}

// ============================================
// Validation Types
// ============================================

/**
 * Result of skill name or description validation
 */
export interface SkillValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validation rules for skill fields
 */
export interface SkillValidationRules {
  nameMaxLength: number;
  namePattern: RegExp;
  descriptionMaxLength: number;
  reservedWords: string[];
}

// ============================================
// File Operation Types
// ============================================

/**
 * Result of skill export operation
 */
export interface SkillExportResult {
  success: boolean;
  path?: string;
  error?: string;
}

/**
 * Result of skill file read operation
 */
export interface SkillReadResult {
  success: boolean;
  content?: SkillContent;
  error?: string;
}

/**
 * Result of skills list operation
 */
export interface SkillsListResult {
  success: boolean;
  skills?: string[];
  error?: string;
}

// ============================================
// Generation Types
// ============================================

/**
 * Source data for skill generation from project index
 */
export interface SkillGenerationSource {
  /** Service information from project index */
  services?: Array<{
    name: string;
    type?: string;
    language?: string;
    framework?: string;
    path: string;
  }>;
  /** Database models from project index */
  databases?: Array<{
    serviceName: string;
    modelName: string;
    orm?: string;
    fields: Record<string, unknown>;
  }>;
  /** API routes from project index */
  apis?: Array<{
    serviceName: string;
    path: string;
    methods: string[];
    framework?: string;
  }>;
  /** CI/CD workflows from project index */
  ciWorkflows?: Array<{
    name: string;
    path: string;
    type: string;
  }>;
}

/**
 * Options for skill generation
 */
export interface SkillGenerationOptions {
  /** Include service skills */
  includeServices?: boolean;
  /** Include database model skills */
  includeDatabases?: boolean;
  /** Include API route skills */
  includeApis?: boolean;
  /** Include CI/CD workflow skills */
  includeCiWorkflows?: boolean;
  /** Auto-enable generated skills */
  autoEnable?: boolean;
}

/**
 * Result of skill generation operation
 */
export interface SkillGenerationResult {
  success: boolean;
  skills: Skill[];
  errors?: Array<{
    source: string;
    error: string;
  }>;
}

/**
 * Options for prompt-based skill generation
 */
export interface SkillPromptGenerationOptions {
  /** The skill name (lowercase, hyphens allowed) */
  name: string;
  /** Natural language prompt describing the skill */
  prompt: string;
}

/**
 * Result of prompt-based skill generation
 */
export interface SkillPromptGenerationResult {
  success: boolean;
  skill?: Skill;
  error?: string;
}
