import { create } from 'zustand';
import type { Skill, SkillGenerationOptions } from '../../shared/types/skills';

interface SkillsState {
  // Skills data
  skills: Skill[];
  skillsLoading: boolean;
  skillsError: string | null;

  // Generation state
  generationLoading: boolean;
  generationError: string | null;

  // Export state
  exportLoading: boolean;
  exportError: string | null;

  // Filter/search
  filterSource: string | null;
  searchQuery: string;

  // Actions
  setSkills: (skills: Skill[]) => void;
  setSkillsLoading: (loading: boolean) => void;
  setSkillsError: (error: string | null) => void;
  setGenerationLoading: (loading: boolean) => void;
  setGenerationError: (error: string | null) => void;
  setExportLoading: (loading: boolean) => void;
  setExportError: (error: string | null) => void;
  setFilterSource: (source: string | null) => void;
  setSearchQuery: (query: string) => void;
  toggleSkill: (id: string) => void;
  updateSkill: (id: string, updates: Partial<Skill>) => void;
  addSkill: (skill: Skill) => void;
  removeSkill: (id: string) => void;
  clearAll: () => void;
}

export const useSkillsStore = create<SkillsState>((set) => ({
  // Skills data
  skills: [],
  skillsLoading: false,
  skillsError: null,

  // Generation state
  generationLoading: false,
  generationError: null,

  // Export state
  exportLoading: false,
  exportError: null,

  // Filter/search
  filterSource: null,
  searchQuery: '',

  // Actions
  setSkills: (skills) => set({ skills }),
  setSkillsLoading: (loading) => set({ skillsLoading: loading }),
  setSkillsError: (error) => set({ skillsError: error }),
  setGenerationLoading: (loading) => set({ generationLoading: loading }),
  setGenerationError: (error) => set({ generationError: error }),
  setExportLoading: (loading) => set({ exportLoading: loading }),
  setExportError: (error) => set({ exportError: error }),
  setFilterSource: (source) => set({ filterSource: source }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  toggleSkill: (id) =>
    set((state) => ({
      skills: state.skills.map((skill) =>
        skill.id === id ? { ...skill, enabled: !skill.enabled } : skill
      )
    })),
  updateSkill: (id, updates) =>
    set((state) => ({
      skills: state.skills.map((skill) =>
        skill.id === id ? { ...skill, ...updates } : skill
      )
    })),
  addSkill: (skill) =>
    set((state) => ({
      skills: [...state.skills, skill]
    })),
  removeSkill: (id) =>
    set((state) => ({
      skills: state.skills.filter((skill) => skill.id !== id)
    })),
  clearAll: () =>
    set({
      skills: [],
      skillsLoading: false,
      skillsError: null,
      generationLoading: false,
      generationError: null,
      exportLoading: false,
      exportError: null,
      filterSource: null,
      searchQuery: ''
    })
}));

/**
 * Generate skills from project index
 */
export async function generateSkills(
  projectId: string,
  options: SkillGenerationOptions = {}
): Promise<void> {
  const store = useSkillsStore.getState();
  store.setGenerationLoading(true);
  store.setGenerationError(null);

  try {
    const result = await window.electronAPI.generateSkills(projectId, options);
    if (result.success && result.data) {
      store.setSkills(result.data.skills);
    } else {
      store.setGenerationError(result.error || 'Failed to generate skills');
    }
  } catch (error) {
    store.setGenerationError(error instanceof Error ? error.message : 'Unknown error');
  } finally {
    store.setGenerationLoading(false);
  }
}

/**
 * Load existing skills from .claude/skills/ directory
 * This first gets the list of skill names, then fetches full content for each
 */
export async function loadSkills(projectId: string): Promise<void> {
  const store = useSkillsStore.getState();
  store.setSkillsLoading(true);
  store.setSkillsError(null);

  try {
    // First, get the list of skill names
    const listResult = await window.electronAPI.loadSkills(projectId);
    if (!listResult.success || !listResult.data) {
      // No skills found is not an error - just set empty array
      if (listResult.error?.includes('ENOENT') || listResult.error?.includes('not found')) {
        store.setSkills([]);
      } else {
        store.setSkillsError(listResult.error || 'Failed to load skills');
      }
      return;
    }

    // listResult.data is { success: boolean, skills: string[] }
    const skillNames = listResult.data.skills || [];
    if (skillNames.length === 0) {
      store.setSkills([]);
      return;
    }

    // Fetch full content for each skill
    const skills: Skill[] = [];
    for (const skillName of skillNames) {
      try {
        const skillResult = await window.electronAPI.getSkill(projectId, skillName);
        if (skillResult.success && skillResult.data?.content) {
          const content = skillResult.data.content;
          skills.push({
            id: `loaded-${skillName}-${Date.now()}`,
            name: content.metadata.name || skillName,
            description: content.metadata.description || '',
            enabled: true, // Default to enabled for loaded skills
            source: 'ai' as const, // Assume AI source for loaded skills
            metadata: {
              loadedFrom: 'disk',
              loadedAt: new Date().toISOString(),
              version: content.metadata.version,
              'disable-model-invocation': content.metadata['disable-model-invocation'],
              'allowed-tools': content.metadata['allowed-tools']
            },
            instructions: content.instructions
          });
        }
      } catch (err) {
        console.warn(`Failed to load skill ${skillName}:`, err);
        // Continue loading other skills
      }
    }

    store.setSkills(skills);
  } catch (error) {
    store.setSkillsError(error instanceof Error ? error.message : 'Unknown error');
  } finally {
    store.setSkillsLoading(false);
  }
}

/**
 * Export enabled skills to .claude/skills/ directory
 */
export async function exportSkills(projectId: string): Promise<void> {
  const store = useSkillsStore.getState();
  store.setExportLoading(true);
  store.setExportError(null);

  const enabledSkills = store.skills.filter((skill) => skill.enabled);

  try {
    const result = await window.electronAPI.exportSkills(projectId, enabledSkills);
    if (!result.success) {
      store.setExportError(result.error || 'Failed to export skills');
    }
  } catch (error) {
    store.setExportError(error instanceof Error ? error.message : 'Unknown error');
  } finally {
    store.setExportLoading(false);
  }
}

/**
 * Export a single skill to .claude/skills/ directory
 */
export async function exportSingleSkill(
  projectId: string,
  skill: Skill
): Promise<boolean> {
  const store = useSkillsStore.getState();
  store.setExportLoading(true);
  store.setExportError(null);

  try {
    const result = await window.electronAPI.exportSkill(projectId, skill);
    if (!result.success) {
      store.setExportError(result.error || 'Failed to export skill');
      return false;
    }
    return true;
  } catch (error) {
    store.setExportError(error instanceof Error ? error.message : 'Unknown error');
    return false;
  } finally {
    store.setExportLoading(false);
  }
}
