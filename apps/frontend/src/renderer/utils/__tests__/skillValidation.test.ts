/**
 * Skill Validation Tests
 * ==================
 * Tests for skill name and description validation utilities
 * according to Claude Agent Skills specification
 */

import { describe, it, expect } from 'vitest';
import {
  validateSkillName,
  validateSkillDescription,
  validateSkill,
  DEFAULT_VALIDATION_RULES,
} from '../skillValidation';

describe('validateSkillName', () => {
  describe('valid names', () => {
    it('accepts lowercase letters only', () => {
      const result = validateSkillName('myskill');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts lowercase letters and numbers', () => {
      const result = validateSkillName('skill123');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts lowercase letters with hyphens', () => {
      const result = validateSkillName('my-skill');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts complex valid names', () => {
      const result = validateSkillName('service-api-v2');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts names at max length (64 chars)', () => {
      const maxLengthName = 'a'.repeat(64);
      const result = validateSkillName(maxLengthName);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });
  });

  describe('invalid names - empty or missing', () => {
    it('rejects empty string', () => {
      const result = validateSkillName('');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name is required');
    });

    it('rejects whitespace only', () => {
      const result = validateSkillName('   ');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });
  });

  describe('invalid names - length', () => {
    it('rejects names over 64 characters', () => {
      const tooLongName = 'a'.repeat(65);
      const result = validateSkillName(tooLongName);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must be 64 characters or less');
    });
  });

  describe('invalid names - character restrictions', () => {
    it('rejects uppercase letters', () => {
      const result = validateSkillName('MySkill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });

    it('rejects spaces', () => {
      const result = validateSkillName('my skill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });

    it('rejects underscores', () => {
      const result = validateSkillName('my_skill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });

    it('rejects dots', () => {
      const result = validateSkillName('my.skill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });

    it('rejects special characters', () => {
      const result = validateSkillName('my@skill!');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });
  });

  describe('invalid names - reserved words', () => {
    it('rejects names containing "anthropic"', () => {
      const result = validateSkillName('anthropic-skill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name cannot contain reserved words: anthropic, claude');
    });

    it('rejects names containing "claude"', () => {
      const result = validateSkillName('claude-helper');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name cannot contain reserved words: anthropic, claude');
    });

    it('rejects names with reserved words in the middle', () => {
      const result = validateSkillName('my-claude-skill');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name cannot contain reserved words: anthropic, claude');
    });
  });

  describe('custom validation rules', () => {
    it('respects custom max length', () => {
      const customRules = {
        ...DEFAULT_VALIDATION_RULES,
        nameMaxLength: 10,
      };
      const result = validateSkillName('verylongname', customRules);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must be 10 characters or less');
    });

    it('respects custom pattern', () => {
      const customRules = {
        ...DEFAULT_VALIDATION_RULES,
        namePattern: /^[a-z]+$/, // Only lowercase letters, no numbers or hyphens
      };
      const result = validateSkillName('skill-123', customRules);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });

    it('respects custom reserved words', () => {
      const customRules = {
        ...DEFAULT_VALIDATION_RULES,
        reservedWords: ['test', 'demo'],
      };
      const result = validateSkillName('test-skill', customRules);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name cannot contain reserved words: test, demo');
    });
  });
});

describe('validateSkillDescription', () => {
  describe('valid descriptions', () => {
    it('accepts short descriptions', () => {
      const result = validateSkillDescription('A simple skill');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts descriptions with special characters', () => {
      const result = validateSkillDescription('Skill for API calls (REST/GraphQL)');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts descriptions at max length (1024 chars)', () => {
      const maxLengthDesc = 'a'.repeat(1024);
      const result = validateSkillDescription(maxLengthDesc);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts multi-line descriptions', () => {
      const result = validateSkillDescription('Line 1\nLine 2\nLine 3');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });
  });

  describe('invalid descriptions - empty or missing', () => {
    it('rejects empty string', () => {
      const result = validateSkillDescription('');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description is required');
    });

    it('rejects whitespace only', () => {
      const result = validateSkillDescription('   \n   ');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description is required');
    });
  });

  describe('invalid descriptions - length', () => {
    it('rejects descriptions over 1024 characters', () => {
      const tooLongDesc = 'a'.repeat(1025);
      const result = validateSkillDescription(tooLongDesc);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description must be 1024 characters or less');
    });
  });

  describe('custom validation rules', () => {
    it('respects custom max length', () => {
      const customRules = {
        ...DEFAULT_VALIDATION_RULES,
        descriptionMaxLength: 50,
      };
      const longDesc = 'a'.repeat(51);
      const result = validateSkillDescription(longDesc, customRules);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description must be 50 characters or less');
    });
  });
});

describe('validateSkill', () => {
  describe('valid skill data', () => {
    it('accepts valid name and description', () => {
      const result = validateSkill('my-skill', 'A helpful skill for testing');
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('accepts name and description at max lengths', () => {
      const maxName = 'a'.repeat(64);
      const maxDesc = 'b'.repeat(1024);
      const result = validateSkill(maxName, maxDesc);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });
  });

  describe('invalid skill data - name errors first', () => {
    it('returns name error when name is invalid', () => {
      const result = validateSkill('', 'Valid description');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name is required');
    });

    it('returns name error even if description is also invalid', () => {
      const result = validateSkill('', '');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name is required');
    });

    it('returns name error for invalid characters', () => {
      const result = validateSkill('Invalid Name', 'Valid description');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Name must contain only lowercase letters, numbers, and hyphens');
    });
  });

  describe('invalid skill data - description errors', () => {
    it('returns description error when name is valid but description is invalid', () => {
      const result = validateSkill('valid-name', '');
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description is required');
    });

    it('returns description error for too long description', () => {
      const tooLongDesc = 'a'.repeat(1025);
      const result = validateSkill('valid-name', tooLongDesc);
      expect(result.valid).toBe(false);
      expect(result.error).toBe('Description must be 1024 characters or less');
    });
  });

  describe('custom validation rules', () => {
    it('respects custom rules for both fields', () => {
      const customRules = {
        nameMaxLength: 10,
        namePattern: /^[a-z0-9-]+$/,
        descriptionMaxLength: 50,
        reservedWords: ['test'],
      };

      const result1 = validateSkill('verylongname', 'Valid description', customRules);
      expect(result1.valid).toBe(false);
      expect(result1.error).toBe('Name must be 10 characters or less');

      const result2 = validateSkill('short', 'a'.repeat(51), customRules);
      expect(result2.valid).toBe(false);
      expect(result2.error).toBe('Description must be 50 characters or less');
    });
  });
});
