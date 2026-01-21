/**
 * Claude Usage Dropdown - Real-time usage display for Kanban board
 *
 * Displays current session/weekly usage with color-coded status indicator.
 * Shows detailed breakdown with progress bars in dropdown menu.
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, User } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '../ui/dropdown-menu';
import type { ClaudeUsageSnapshot, ClaudeProfile } from '../../../shared/types/agent';

export function ClaudeUsageDropdown() {
  const [usage, setUsage] = useState<ClaudeUsageSnapshot | null>(null);
  const [activeProfile, setActiveProfile] = useState<ClaudeProfile | null>(null);

  useEffect(() => {
    // Load initial profile
    window.electronAPI.getClaudeProfiles().then((result) => {
      if (result.success && result.data) {
        const profile = result.data.profiles.find(p => p.id === result.data!.activeProfileId);
        if (profile) {
          setActiveProfile(profile);
        }
      }
    });

    // Listen for usage updates from main process
    const unsubscribe = window.electronAPI.onUsageUpdated((snapshot: ClaudeUsageSnapshot) => {
      setUsage(snapshot);
    });

    // Request initial usage on mount
    window.electronAPI.requestUsageUpdate().then((result) => {
      if (result.success && result.data) {
        setUsage(result.data);
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Don't render if no active profile
  if (!activeProfile) {
    return null;
  }

  // Use usage data if available, otherwise show profile without usage
  const profileName = usage?.profileName || activeProfile.name;
  const hasUsage = usage !== null;

  // Determine color based on highest usage percentage
  const maxUsage = hasUsage ? Math.max(usage.sessionPercent, usage.weeklyPercent) : 0;

  // Color thresholds: green (<60%), yellow (60-80%), orange (80-95%), red (>95%)
  const getColorClasses = (percent: number) => {
    if (percent > 95) return 'bg-red-500';
    if (percent >= 80) return 'bg-orange-500';
    if (percent >= 60) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  // Gray dot when no usage data, colored when we have data
  const statusDotColor = hasUsage ? getColorClasses(maxUsage) : 'bg-muted-foreground/50';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors rounded-md hover:bg-accent"
          aria-label="Claude usage status"
        >
          {/* Status dot */}
          <span
            className={`h-2 w-2 rounded-full ${statusDotColor}`}
            aria-hidden="true"
          />

          {/* Profile name */}
          <span className="max-w-[150px] truncate">
            {profileName}
          </span>

          {/* Chevron icon */}
          <ChevronDown className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" side="bottom" className="w-64">
        {hasUsage ? (
          <>
            {/* Session usage section */}
            <div className="px-2 py-2">
              <div className="flex items-center justify-between gap-4 mb-2">
                <DropdownMenuLabel className="p-0 text-sm font-semibold">
                  Session Usage
                </DropdownMenuLabel>
                <span className="text-sm font-semibold tabular-nums">
                  {Math.round(usage.sessionPercent)}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-2 w-full rounded-full overflow-hidden bg-muted mb-1.5">
                <div
                  className={`h-full transition-all ${getColorClasses(usage.sessionPercent)}`}
                  style={{ width: `${Math.min(usage.sessionPercent, 100)}%` }}
                />
              </div>

              {/* Reset time */}
              {usage.sessionResetTime && (
                <div className="text-xs text-muted-foreground">
                  Resets: {usage.sessionResetTime}
                </div>
              )}
            </div>

            <DropdownMenuSeparator />

            {/* Weekly usage section */}
            <div className="px-2 py-2">
              <div className="flex items-center justify-between gap-4 mb-2">
                <DropdownMenuLabel className="p-0 text-sm font-semibold">
                  Weekly Usage
                </DropdownMenuLabel>
                <span className="text-sm font-semibold tabular-nums">
                  {Math.round(usage.weeklyPercent)}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-2 w-full rounded-full overflow-hidden bg-muted mb-1.5">
                <div
                  className={`h-full transition-all ${getColorClasses(usage.weeklyPercent)}`}
                  style={{ width: `${Math.min(usage.weeklyPercent, 100)}%` }}
                />
              </div>

              {/* Reset time */}
              {usage.weeklyResetTime && (
                <div className="text-xs text-muted-foreground">
                  Resets: {usage.weeklyResetTime}
                </div>
              )}
            </div>
          </>
        ) : (
          /* No usage data yet - show profile info */
          <div className="px-2 py-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <User className="h-4 w-4" />
              <span className="text-sm">Active Profile</span>
            </div>
            <div className="mt-1 text-sm font-medium">{profileName}</div>
            <div className="mt-2 text-xs text-muted-foreground">
              Usage data will appear when a Claude session is active
            </div>
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
