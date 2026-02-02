import { create } from 'zustand';
import type {
  SessionHistoryEntry,
  SessionMetrics,
  SessionStatus
} from '../../shared/types';
import { debugLog } from '../../shared/utils/debug-logger';

interface SessionHistoryFilters {
  searchText: string;
  statusFilter: SessionStatus | 'all';
  sortBy: 'date' | 'duration' | 'title';
  sortOrder: 'asc' | 'desc';
}

interface SessionHistoryState {
  // Data
  entries: SessionHistoryEntry[];
  metrics: SessionMetrics | null;
  isLoading: boolean;
  isLoadingMetrics: boolean;
  error: string | null;

  // Filters
  filters: SessionHistoryFilters;

  // Actions
  setEntries: (entries: SessionHistoryEntry[]) => void;
  setMetrics: (metrics: SessionMetrics | null) => void;
  setLoading: (loading: boolean) => void;
  setLoadingMetrics: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSearchText: (text: string) => void;
  setStatusFilter: (status: SessionStatus | 'all') => void;
  setSortBy: (sortBy: 'date' | 'duration' | 'title') => void;
  setSortOrder: (order: 'asc' | 'desc') => void;
  clearFilters: () => void;
  clear: () => void;

  // Selectors
  getFilteredEntries: () => SessionHistoryEntry[];
}

const DEFAULT_FILTERS: SessionHistoryFilters = {
  searchText: '',
  statusFilter: 'all',
  sortBy: 'date',
  sortOrder: 'desc'
};

function matchesSearch(entry: SessionHistoryEntry, searchText: string): boolean {
  if (!searchText) return true;
  const lower = searchText.toLowerCase();
  return (
    entry.title.toLowerCase().includes(lower) ||
    entry.specId.toLowerCase().includes(lower) ||
    entry.id.toLowerCase().includes(lower)
  );
}

function matchesStatus(entry: SessionHistoryEntry, statusFilter: SessionStatus | 'all'): boolean {
  if (statusFilter === 'all') return true;
  return entry.status === statusFilter;
}

function sortEntries(
  entries: SessionHistoryEntry[],
  sortBy: 'date' | 'duration' | 'title',
  sortOrder: 'asc' | 'desc'
): SessionHistoryEntry[] {
  const sorted = [...entries].sort((a, b) => {
    switch (sortBy) {
      case 'date': {
        const dateA = new Date(a.updatedAt || a.createdAt).getTime();
        const dateB = new Date(b.updatedAt || b.createdAt).getTime();
        return dateA - dateB;
      }
      case 'duration':
        return a.durationMs - b.durationMs;
      case 'title':
        return a.title.localeCompare(b.title);
      default:
        return 0;
    }
  });

  return sortOrder === 'desc' ? sorted.reverse() : sorted;
}

export const useSessionHistoryStore = create<SessionHistoryState>((set, get) => ({
  // Initial state
  entries: [],
  metrics: null,
  isLoading: false,
  isLoadingMetrics: false,
  error: null,
  filters: { ...DEFAULT_FILTERS },

  // Actions
  setEntries: (entries) => set({ entries, error: null }),

  setMetrics: (metrics) => set({ metrics }),

  setLoading: (loading) => set({ isLoading: loading }),

  setLoadingMetrics: (loading) => set({ isLoadingMetrics: loading }),

  setError: (error) => set({ error }),

  setSearchText: (text) =>
    set((state) => ({
      filters: { ...state.filters, searchText: text }
    })),

  setStatusFilter: (status) =>
    set((state) => ({
      filters: { ...state.filters, statusFilter: status }
    })),

  setSortBy: (sortBy) =>
    set((state) => ({
      filters: { ...state.filters, sortBy }
    })),

  setSortOrder: (order) =>
    set((state) => ({
      filters: { ...state.filters, sortOrder: order }
    })),

  clearFilters: () => set({ filters: { ...DEFAULT_FILTERS } }),

  clear: () =>
    set({
      entries: [],
      metrics: null,
      isLoading: false,
      isLoadingMetrics: false,
      error: null,
      filters: { ...DEFAULT_FILTERS }
    }),

  // Selectors
  getFilteredEntries: () => {
    const { entries, filters } = get();
    const filtered = entries.filter(
      (entry) =>
        matchesSearch(entry, filters.searchText) &&
        matchesStatus(entry, filters.statusFilter)
    );
    return sortEntries(filtered, filters.sortBy, filters.sortOrder);
  }
}));

// Helper functions (called from components/hooks)

export async function loadSessionHistory(projectId: string): Promise<void> {
  const store = useSessionHistoryStore.getState();
  store.setLoading(true);
  store.setError(null);

  try {
    const result = await window.electronAPI.listSessionHistory(projectId);
    if (result.success) {
      store.setEntries(result.data ?? []);
    } else {
      debugLog('[SessionHistoryStore] Failed to load history:', result.error);
      store.setError(result.error ?? 'Unknown error');
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load session history';
    debugLog('[SessionHistoryStore] Error loading history:', message);
    store.setError(message);
  } finally {
    store.setLoading(false);
  }
}

export async function loadSessionMetrics(projectId: string): Promise<void> {
  const store = useSessionHistoryStore.getState();
  store.setLoadingMetrics(true);

  try {
    const result = await window.electronAPI.getSessionMetrics(projectId);
    if (result.success) {
      store.setMetrics(result.data ?? null);
    } else {
      debugLog('[SessionHistoryStore] Failed to load metrics:', result.error);
    }
  } catch (err) {
    debugLog('[SessionHistoryStore] Error loading metrics:', err);
  } finally {
    store.setLoadingMetrics(false);
  }
}

export async function deleteSessionHistoryEntry(
  projectId: string,
  sessionId: string
): Promise<boolean> {
  try {
    const result = await window.electronAPI.deleteSessionHistory(projectId, sessionId);
    if (result.success) {
      const store = useSessionHistoryStore.getState();
      store.setEntries(store.entries.filter((e) => e.id !== sessionId));
      return true;
    }
    debugLog('[SessionHistoryStore] Failed to delete entry:', result.error);
    return false;
  } catch (err) {
    debugLog('[SessionHistoryStore] Error deleting entry:', err);
    return false;
  }
}

export async function persistCompletedSession(
  projectId: string,
  sessionId: string
): Promise<SessionHistoryEntry | null> {
  try {
    const result = await window.electronAPI.loadSessionHistory(projectId, sessionId);
    if (result.success) {
      // Refresh the full list after persisting
      await loadSessionHistory(projectId);
      return result.data ?? null;
    }
    debugLog('[SessionHistoryStore] Failed to persist session:', result.error);
    return null;
  } catch (err) {
    debugLog('[SessionHistoryStore] Error persisting session:', err);
    return null;
  }
}
