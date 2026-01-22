/**
 * Skill validation utilities for Claude Agent Skills
 */

import type { SkillValidationResult, SkillValidationRules } from '../../shared/types/skills';

/**
 * Default validation rules for skills
 */
export const DEFAULT_VALIDATION_RULES: SkillValidationRules = {
  nameMaxLength: 64,
  namePattern: /^[a-z0-9-]+$/,
  descriptionMaxLength: 1024,
  reservedWords: ['anthropic', 'claude'],
};

/**
 * Validate a skill name according to Claude Agent Skills specification
 *
 * Rules:
 * - Required (non-empty)
 * - Max 64 characters
 * - Lowercase letters, numbers, and hyphens only
 * - Cannot contain reserved words: anthropic, claude
 *
 * @param name - The skill name to validate
 * @param rules - Optional custom validation rules (defaults to DEFAULT_VALIDATION_RULES)
 * @returns Validation result with valid flag and optional error message
 */
export function validateSkillName(
  name: string,
  rules: SkillValidationRules = DEFAULT_VALIDATION_RULES,
): SkillValidationResult {
  // Check if name is provided
  if (!name || name.length === 0) {
    return { valid: false, error: 'Name is required' };
  }

  // Check max length
  if (name.length > rules.nameMaxLength) {
    return {
      valid: false,
      error: `Name must be ${rules.nameMaxLength} characters or less`,
    };
  }

  // Check pattern (lowercase letters, numbers, hyphens only)
  if (!rules.namePattern.test(name)) {
    return {
      valid: false,
      error: 'Name must contain only lowercase letters, numbers, and hyphens',
    };
  }

  // Check for reserved words
  const lowerName = name.toLowerCase();
  for (const word of rules.reservedWords) {
    if (lowerName.includes(word)) {
      return {
        valid: false,
        error: `Name cannot contain reserved words: ${rules.reservedWords.join(', ')}`,
      };
    }
  }

  return { valid: true };
}

/**
 * Validate a skill description according to Claude Agent Skills specification
 *
 * Rules:
 * - Required (non-empty)
 * - Max 1024 characters
 *
 * @param description - The skill description to validate
 * @param rules - Optional custom validation rules (defaults to DEFAULT_VALIDATION_RULES)
 * @returns Validation result with valid flag and optional error message
 */
export function validateSkillDescription(
  description: string,
  rules: SkillValidationRules = DEFAULT_VALIDATION_RULES,
): SkillValidationResult {
  // Check if description is provided
  if (!description || description.trim().length === 0) {
    return { valid: false, error: 'Description is required' };
  }

  // Check max length
  if (description.length > rules.descriptionMaxLength) {
    return {
      valid: false,
      error: `Description must be ${rules.descriptionMaxLength} characters or less`,
    };
  }

  return { valid: true };
}

/**
 * Validate both skill name and description
 *
 * @param name - The skill name to validate
 * @param description - The skill description to validate
 * @param rules - Optional custom validation rules (defaults to DEFAULT_VALIDATION_RULES)
 * @returns Validation result for both fields. If either fails, valid is false and error contains first error encountered.
 */
export function validateSkill(
  name: string,
  description: string,
  rules: SkillValidationRules = DEFAULT_VALIDATION_RULES,
): SkillValidationResult {
  // Validate name first
  const nameResult = validateSkillName(name, rules);
  if (!nameResult.valid) {
    return nameResult;
  }

  // Validate description
  const descriptionResult = validateSkillDescription(description, rules);
  if (!descriptionResult.valid) {
    return descriptionResult;
  }

  return { valid: true };
}
