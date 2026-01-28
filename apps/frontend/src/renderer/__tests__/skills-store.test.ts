/**
 * Unit tests for Skills Store
 * Tests Zustand store for skills state management
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useSkillsStore } from '../stores/skills-store';
import type { Skill, SkillSource } from '../../shared/types/skills';

// Helper to create test skills
function createTestSkill(overrides: Partial<Skill> = {}): Skill {
  return {
    id: `skill-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    name: 'test-skill',
    description: 'Test skill description',
    enabled: false,
    source: 'service' as SkillSource,
    metadata: {},
    instructions: '## Usage\n\nTest instructions',
    ...overrides
  };
}

describe('Skills Store', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useSkillsStore.setState({
      skills: [],
      skillsLoading: false,
      skillsError: null,
      generationLoading: false,
      generationError: null,
      exportLoading: false,
      exportError: null,
      filterSource: null,
      searchQuery: ''
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('setSkills', () => {
    it('should set skills', () => {
      const skills = [
        createTestSkill({ id: 'skill-1', name: 'skill-one' }),
        createTestSkill({ id: 'skill-2', name: 'skill-two' })
      ];

      useSkillsStore.getState().setSkills(skills);

      expect(useSkillsStore.getState().skills).toHaveLength(2);
      expect(useSkillsStore.getState().skills[0].id).toBe('skill-1');
      expect(useSkillsStore.getState().skills[1].id).toBe('skill-2');
    });

    it('should replace existing skills', () => {
      const initialSkills = [createTestSkill({ id: 'skill-1' })];
      useSkillsStore.setState({ skills: initialSkills });

      const newSkills = [
        createTestSkill({ id: 'skill-2' }),
        createTestSkill({ id: 'skill-3' })
      ];
      useSkillsStore.getState().setSkills(newSkills);

      expect(useSkillsStore.getState().skills).toHaveLength(2);
      expect(useSkillsStore.getState().skills[0].id).toBe('skill-2');
    });

    it('should clear skills with empty array', () => {
      useSkillsStore.setState({ skills: [createTestSkill()] });

      useSkillsStore.getState().setSkills([]);

      expect(useSkillsStore.getState().skills).toHaveLength(0);
    });
  });

  describe('toggleSkill', () => {
    it('should toggle skill enabled state from false to true', () => {
      const skills = [
        createTestSkill({ id: 'skill-1', enabled: false }),
        createTestSkill({ id: 'skill-2', enabled: false })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().toggleSkill('skill-1');

      const state = useSkillsStore.getState();
      expect(state.skills[0].enabled).toBe(true);
      expect(state.skills[1].enabled).toBe(false);
    });

    it('should toggle skill enabled state from true to false', () => {
      const skills = [createTestSkill({ id: 'skill-1', enabled: true })];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().toggleSkill('skill-1');

      expect(useSkillsStore.getState().skills[0].enabled).toBe(false);
    });

    it('should not affect other skills', () => {
      const skills = [
        createTestSkill({ id: 'skill-1', enabled: false }),
        createTestSkill({ id: 'skill-2', enabled: true }),
        createTestSkill({ id: 'skill-3', enabled: false })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().toggleSkill('skill-2');

      const state = useSkillsStore.getState();
      expect(state.skills[0].enabled).toBe(false);
      expect(state.skills[1].enabled).toBe(false);
      expect(state.skills[2].enabled).toBe(false);
    });

    it('should do nothing for non-existent skill', () => {
      const skills = [createTestSkill({ id: 'skill-1', enabled: false })];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().toggleSkill('nonexistent');

      expect(useSkillsStore.getState().skills[0].enabled).toBe(false);
    });
  });

  describe('updateSkill', () => {
    it('should update skill properties', () => {
      const skills = [
        createTestSkill({
          id: 'skill-1',
          name: 'old-name',
          description: 'Old description'
        })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().updateSkill('skill-1', {
        name: 'new-name',
        description: 'New description'
      });

      const state = useSkillsStore.getState();
      expect(state.skills[0].name).toBe('new-name');
      expect(state.skills[0].description).toBe('New description');
    });

    it('should update only specified properties', () => {
      const skills = [
        createTestSkill({
          id: 'skill-1',
          name: 'original-name',
          description: 'Original description',
          enabled: false
        })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().updateSkill('skill-1', {
        description: 'Updated description'
      });

      const state = useSkillsStore.getState();
      expect(state.skills[0].name).toBe('original-name');
      expect(state.skills[0].description).toBe('Updated description');
      expect(state.skills[0].enabled).toBe(false);
    });

    it('should not affect other skills', () => {
      const skills = [
        createTestSkill({ id: 'skill-1', name: 'skill-one' }),
        createTestSkill({ id: 'skill-2', name: 'skill-two' }),
        createTestSkill({ id: 'skill-3', name: 'skill-three' })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().updateSkill('skill-2', { name: 'updated-skill-two' });

      const state = useSkillsStore.getState();
      expect(state.skills[0].name).toBe('skill-one');
      expect(state.skills[1].name).toBe('updated-skill-two');
      expect(state.skills[2].name).toBe('skill-three');
    });

    it('should do nothing for non-existent skill', () => {
      const skills = [createTestSkill({ id: 'skill-1', name: 'original' })];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().updateSkill('nonexistent', { name: 'updated' });

      expect(useSkillsStore.getState().skills[0].name).toBe('original');
    });
  });

  describe('addSkill', () => {
    it('should add a new skill', () => {
      const newSkill = createTestSkill({ id: 'skill-1', name: 'new-skill' });

      useSkillsStore.getState().addSkill(newSkill);

      expect(useSkillsStore.getState().skills).toHaveLength(1);
      expect(useSkillsStore.getState().skills[0].id).toBe('skill-1');
    });

    it('should append to existing skills', () => {
      const existingSkills = [
        createTestSkill({ id: 'skill-1' }),
        createTestSkill({ id: 'skill-2' })
      ];
      useSkillsStore.setState({ skills: existingSkills });

      const newSkill = createTestSkill({ id: 'skill-3' });
      useSkillsStore.getState().addSkill(newSkill);

      expect(useSkillsStore.getState().skills).toHaveLength(3);
      expect(useSkillsStore.getState().skills[2].id).toBe('skill-3');
    });
  });

  describe('removeSkill', () => {
    it('should remove skill by id', () => {
      const skills = [
        createTestSkill({ id: 'skill-1' }),
        createTestSkill({ id: 'skill-2' }),
        createTestSkill({ id: 'skill-3' })
      ];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().removeSkill('skill-2');

      const state = useSkillsStore.getState();
      expect(state.skills).toHaveLength(2);
      expect(state.skills.find((s) => s.id === 'skill-2')).toBeUndefined();
    });

    it('should do nothing for non-existent skill', () => {
      const skills = [createTestSkill({ id: 'skill-1' })];
      useSkillsStore.setState({ skills });

      useSkillsStore.getState().removeSkill('nonexistent');

      expect(useSkillsStore.getState().skills).toHaveLength(1);
    });
  });

  describe('setSkillsLoading', () => {
    it('should set skillsLoading state', () => {
      useSkillsStore.getState().setSkillsLoading(true);
      expect(useSkillsStore.getState().skillsLoading).toBe(true);

      useSkillsStore.getState().setSkillsLoading(false);
      expect(useSkillsStore.getState().skillsLoading).toBe(false);
    });
  });

  describe('setSkillsError', () => {
    it('should set skillsError state', () => {
      useSkillsStore.getState().setSkillsError('Test error');
      expect(useSkillsStore.getState().skillsError).toBe('Test error');

      useSkillsStore.getState().setSkillsError(null);
      expect(useSkillsStore.getState().skillsError).toBeNull();
    });
  });

  describe('setGenerationLoading', () => {
    it('should set generationLoading state', () => {
      useSkillsStore.getState().setGenerationLoading(true);
      expect(useSkillsStore.getState().generationLoading).toBe(true);

      useSkillsStore.getState().setGenerationLoading(false);
      expect(useSkillsStore.getState().generationLoading).toBe(false);
    });
  });

  describe('setGenerationError', () => {
    it('should set generationError state', () => {
      useSkillsStore.getState().setGenerationError('Generation failed');
      expect(useSkillsStore.getState().generationError).toBe('Generation failed');

      useSkillsStore.getState().setGenerationError(null);
      expect(useSkillsStore.getState().generationError).toBeNull();
    });
  });

  describe('setExportLoading', () => {
    it('should set exportLoading state', () => {
      useSkillsStore.getState().setExportLoading(true);
      expect(useSkillsStore.getState().exportLoading).toBe(true);

      useSkillsStore.getState().setExportLoading(false);
      expect(useSkillsStore.getState().exportLoading).toBe(false);
    });
  });

  describe('setExportError', () => {
    it('should set exportError state', () => {
      useSkillsStore.getState().setExportError('Export failed');
      expect(useSkillsStore.getState().exportError).toBe('Export failed');

      useSkillsStore.getState().setExportError(null);
      expect(useSkillsStore.getState().exportError).toBeNull();
    });
  });

  describe('setFilterSource', () => {
    it('should set filterSource', () => {
      useSkillsStore.getState().setFilterSource('service');
      expect(useSkillsStore.getState().filterSource).toBe('service');

      useSkillsStore.getState().setFilterSource(null);
      expect(useSkillsStore.getState().filterSource).toBeNull();
    });
  });

  describe('setSearchQuery', () => {
    it('should set searchQuery', () => {
      useSkillsStore.getState().setSearchQuery('test query');
      expect(useSkillsStore.getState().searchQuery).toBe('test query');

      useSkillsStore.getState().setSearchQuery('');
      expect(useSkillsStore.getState().searchQuery).toBe('');
    });
  });

  describe('clearAll', () => {
    it('should reset all state to initial values', () => {
      // Set some state
      useSkillsStore.setState({
        skills: [createTestSkill()],
        skillsLoading: true,
        skillsError: 'Error',
        generationLoading: true,
        generationError: 'Gen error',
        exportLoading: true,
        exportError: 'Export error',
        filterSource: 'service',
        searchQuery: 'test'
      });

      useSkillsStore.getState().clearAll();

      const state = useSkillsStore.getState();
      expect(state.skills).toHaveLength(0);
      expect(state.skillsLoading).toBe(false);
      expect(state.skillsError).toBeNull();
      expect(state.generationLoading).toBe(false);
      expect(state.generationError).toBeNull();
      expect(state.exportLoading).toBe(false);
      expect(state.exportError).toBeNull();
      expect(state.filterSource).toBeNull();
      expect(state.searchQuery).toBe('');
    });
  });
});
