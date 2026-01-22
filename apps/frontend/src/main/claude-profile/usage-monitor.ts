/**
 * Usage Monitor - Proactive usage monitoring and account switching
 *
 * Monitors Claude account usage at configured intervals and automatically
 * switches to alternative accounts before hitting rate limits.
 *
 * Uses hybrid approach:
 * 1. Primary: Direct OAuth API (https://api.anthropic.com/api/oauth/usage)
 * 2. Fallback: CLI /usage command parsing
 */

import { EventEmitter } from 'events';
import { getClaudeProfileManager } from '../claude-profile-manager';
import { ClaudeUsageSnapshot } from '../../shared/types/agent';

export class UsageMonitor extends EventEmitter {
  private static instance: UsageMonitor;
  private intervalId: NodeJS.Timeout | null = null;
  private currentUsage: ClaudeUsageSnapshot | null = null;
  private isChecking = false;
  private useApiMethod = true; // Try API first, fall back to CLI if it fails
  
  // Swap loop protection: track profiles that recently failed auth
  private authFailedProfiles: Map<string, number> = new Map(); // profileId -> timestamp
  private static AUTH_FAILURE_COOLDOWN_MS = 5 * 60 * 1000; // 5 minutes cooldown
  
  // Debug flag for verbose logging
  private readonly isDebug = process.env.DEBUG === 'true';

  private constructor() {
    super();
    console.warn('[UsageMonitor] Initialized');
  }

  static getInstance(): UsageMonitor {
    if (!UsageMonitor.instance) {
      UsageMonitor.instance = new UsageMonitor();
    }
    return UsageMonitor.instance;
  }

  /**
   * Start monitoring usage at configured interval
   */
  start(): void {
    const profileManager = getClaudeProfileManager();
    const settings = profileManager.getAutoSwitchSettings();

    if (!settings.enabled || !settings.proactiveSwapEnabled) {
      console.warn('[UsageMonitor] Proactive monitoring disabled. Settings:', JSON.stringify(settings, null, 2));
      return;
    }

    if (this.intervalId) {
      console.warn('[UsageMonitor] Already running');
      return;
    }

    const interval = settings.usageCheckInterval || 30000;
    console.warn('[UsageMonitor] Starting with interval:', interval, 'ms');

    // Check immediately
    this.checkUsageAndSwap();

    // Then check periodically
    this.intervalId = setInterval(() => {
      this.checkUsageAndSwap();
    }, interval);
  }

  /**
   * Stop monitoring
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      console.warn('[UsageMonitor] Stopped');
    }
  }

  /**
   * Get current usage snapshot (for UI indicator)
   */
  getCurrentUsage(): ClaudeUsageSnapshot | null {
    return this.currentUsage;
  }

  /**
   * Fetch usage on-demand (for UI requests when proactive monitoring is disabled)
   * This is called by the IPC handler when the UI requests usage data.
   */
  async fetchUsageOnDemand(): Promise<ClaudeUsageSnapshot | null> {
    try {
      const profileManager = getClaudeProfileManager();
      const activeProfile = profileManager.getActiveProfile();

      if (!activeProfile) {
        console.warn('[UsageMonitor] No active profile for on-demand fetch');
        return null;
      }

      // Fetch usage without triggering proactive swap logic
      const decryptedToken = profileManager.getProfileToken(activeProfile.id);
      const usage = await this.fetchUsage(activeProfile.id, decryptedToken ?? undefined);

      if (usage) {
        // Update current usage cache
        this.currentUsage = usage;

        // Emit usage update for UI
        this.emit('usage-updated', usage);

        console.warn('[UsageMonitor] On-demand fetch successful');
      }

      return usage;
    } catch (error) {
      console.error('[UsageMonitor] On-demand fetch failed:', error);
      return null;
    }
  }

  /**
   * Check usage and trigger swap if thresholds exceeded
   */
  private async checkUsageAndSwap(): Promise<void> {
    if (this.isChecking) {
      return; // Prevent concurrent checks
    }

    this.isChecking = true;

    try {
      const profileManager = getClaudeProfileManager();
      const activeProfile = profileManager.getActiveProfile();

      if (!activeProfile) {
        console.warn('[UsageMonitor] No active profile');
        return;
      }

      // Fetch current usage (hybrid approach)
      // Get decrypted token from ProfileManager (activeProfile.oauthToken is encrypted)
      const decryptedToken = profileManager.getProfileToken(activeProfile.id);
      const usage = await this.fetchUsage(activeProfile.id, decryptedToken ?? undefined);
      if (!usage) {
        console.warn('[UsageMonitor] Failed to fetch usage');
        return;
      }

      this.currentUsage = usage;

      // Emit usage update for UI
      this.emit('usage-updated', usage);

      // Check thresholds
      const settings = profileManager.getAutoSwitchSettings();
      const sessionExceeded = usage.sessionPercent >= settings.sessionThreshold;
      const weeklyExceeded = usage.weeklyPercent >= settings.weeklyThreshold;

      if (sessionExceeded || weeklyExceeded) {
        if (this.isDebug) {
          console.warn('[UsageMonitor:TRACE] Threshold exceeded', {
            sessionPercent: usage.sessionPercent,
            weekPercent: usage.weeklyPercent,
            activeProfile: activeProfile.id,
            hasToken: !!decryptedToken
          });
        }

        console.warn('[UsageMonitor] Threshold exceeded:', {
          sessionPercent: usage.sessionPercent,
          sessionThreshold: settings.sessionThreshold,
          weeklyPercent: usage.weeklyPercent,
          weeklyThreshold: settings.weeklyThreshold
        });

        // Attempt proactive swap
        await this.performProactiveSwap(
          activeProfile.id,
          sessionExceeded ? 'session' : 'weekly'
        );
      } else {
        if (this.isDebug) {
          console.warn('[UsageMonitor:TRACE] Usage OK', {
            sessionPercent: usage.sessionPercent,
            weekPercent: usage.weeklyPercent
          });
        }
      }
    } catch (error) {
      // Check for auth failure (401/403) from fetchUsageViaAPI
      if ((error as any).statusCode === 401 || (error as any).statusCode === 403) {
        const profileManager = getClaudeProfileManager();
        const activeProfile = profileManager.getActiveProfile();
        
        if (activeProfile) {
          // Mark this profile as auth-failed to prevent swap loops
          this.authFailedProfiles.set(activeProfile.id, Date.now());
          console.warn('[UsageMonitor] Auth failure detected, marked profile as failed:', activeProfile.id);
          
          // Clean up expired entries from the failed profiles map
          const now = Date.now();
          this.authFailedProfiles.forEach((timestamp, profileId) => {
            if (now - timestamp > UsageMonitor.AUTH_FAILURE_COOLDOWN_MS) {
              this.authFailedProfiles.delete(profileId);
            }
          });
          
          try {
            const excludeProfiles = Array.from(this.authFailedProfiles.keys());
            console.warn('[UsageMonitor] Attempting proactive swap (excluding failed profiles):', excludeProfiles);
            await this.performProactiveSwap(
              activeProfile.id,
              'session', // Treat auth failure as session limit for immediate swap
              excludeProfiles
            );
            return;
          } catch (swapError) {
            console.error('[UsageMonitor] Failed to perform auth-failure swap:', swapError);
          }
        }
      }

      console.error('[UsageMonitor] Check failed:', error);
    } finally {
      this.isChecking = false;
    }
  }

  /**
   * Fetch usage - HYBRID APPROACH
   * Tries API first, falls back to CLI if API fails
   */
  private async fetchUsage(
    profileId: string,
    oauthToken?: string
  ): Promise<ClaudeUsageSnapshot | null> {
    const profileManager = getClaudeProfileManager();
    const profile = profileManager.getProfile(profileId);
    if (!profile) {
      return null;
    }

    // Attempt 1: Direct API call (preferred)
    if (this.useApiMethod && oauthToken) {
      const apiUsage = await this.fetchUsageViaAPI(oauthToken, profileId, profile.name);
      if (apiUsage) {
        console.warn('[UsageMonitor] Successfully fetched via API');
        return apiUsage;
      }

      // API failed - switch to CLI method for future calls
      console.warn('[UsageMonitor] API method failed, falling back to CLI');
      this.useApiMethod = false;
    }

    // Attempt 2: CLI /usage command (fallback)
    return await this.fetchUsageViaCLI(profileId, profile.name);
  }

  /**
   * Fetch usage via OAuth API endpoint
   * Endpoint: https://api.anthropic.com/api/oauth/usage
   */
  private async fetchUsageViaAPI(
    oauthToken: string,
    profileId: string,
    profileName: string
  ): Promise<ClaudeUsageSnapshot | null> {
    try {
      const response = await fetch('https://api.anthropic.com/api/oauth/usage', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${oauthToken}`,
          'Content-Type': 'application/json',
          'anthropic-version': '2023-06-01'
        }
      });

      if (!response.ok) {
        console.error('[UsageMonitor] API error:', response.status, response.statusText);
        // Throw specific error for auth failures so we can trigger a swap
        if (response.status === 401 || response.status === 403) {
          const error = new Error(`API Auth Failure: ${response.status}`);
          (error as any).statusCode = response.status;
          throw error;
        }
        return null;
      }

      const data = await response.json() as {
        five_hour_utilization?: number;
        seven_day_utilization?: number;
        five_hour_reset_at?: string;
        seven_day_reset_at?: string;
      };

      // Expected response format:
      // {
      //   "five_hour_utilization": 0.72,  // 0.0-1.0
      //   "seven_day_utilization": 0.45,  // 0.0-1.0
      //   "five_hour_reset_at": "2025-01-17T15:00:00Z",
      //   "seven_day_reset_at": "2025-01-20T12:00:00Z"
      // }

      return {
        sessionPercent: Math.round((data.five_hour_utilization || 0) * 100),
        weeklyPercent: Math.round((data.seven_day_utilization || 0) * 100),
        sessionResetTime: this.formatResetTime(data.five_hour_reset_at),
        weeklyResetTime: this.formatResetTime(data.seven_day_reset_at),
        profileId,
        profileName,
        fetchedAt: new Date(),
        limitType: (data.seven_day_utilization || 0) > (data.five_hour_utilization || 0)
          ? 'weekly'
          : 'session'
      };
    } catch (error: any) {
      // Re-throw auth failures to be handled by checkUsageAndSwap
      if (error?.statusCode === 401 || error?.statusCode === 403) {
        throw error;
      }
      
      console.error('[UsageMonitor] API fetch failed:', error);
      return null;
    }
  }

  /**
   * Fetch usage via CLI /usage command (fallback)
   * Spawns a Claude process, sends /usage command, and parses the output.
   */
  private async fetchUsageViaCLI(
    profileId: string,
    profileName: string
  ): Promise<ClaudeUsageSnapshot | null> {
    try {
      const { spawn } = await import('child_process');
      const { getClaudeCliInvocationAsync } = await import('../claude-cli-utils');
      const profileManager = getClaudeProfileManager();
      const profile = profileManager.getProfile(profileId);

      if (!profile) {
        console.error('[UsageMonitor] Profile not found:', profileId);
        return null;
      }

      // Get Claude CLI command and environment
      const { command, env } = await getClaudeCliInvocationAsync();

      // Add profile-specific config dir if available
      const profileEnv = { ...env };
      if (profile.configDir) {
        profileEnv.CLAUDE_CODE_CONFIG_DIR = profile.configDir;
      }

      return new Promise((resolve) => {
        const proc = spawn(command, [], { env: profileEnv });
        let output = '';
        let errorOutput = '';

        proc.stdout?.on('data', (data: Buffer) => {
          output += data.toString();
        });

        proc.stderr?.on('data', (data: Buffer) => {
          errorOutput += data.toString();
        });

        proc.on('close', (code) => {
          if (code !== 0) {
            console.error('[UsageMonitor] CLI process exited with code:', code, 'stderr:', errorOutput);
            resolve(null);
            return;
          }

          // Parse the usage output
          const usage = this.parseUsageOutput(output, profileId, profileName);
          if (usage) {
            console.warn('[UsageMonitor] Successfully fetched via CLI');
          } else {
            console.warn('[UsageMonitor] Failed to parse CLI output');
          }
          resolve(usage);
        });

        proc.on('error', (error) => {
          console.error('[UsageMonitor] Failed to spawn Claude CLI:', error);
          resolve(null);
        });

        // Send /usage command after a short delay
        setTimeout(() => {
          proc.stdin?.write('/usage\n');
          // Wait for output, then close stdin
          setTimeout(() => {
            proc.stdin?.write('/exit\n');
            proc.stdin?.end();
          }, 2000);
        }, 1000);
      });
    } catch (error) {
      console.error('[UsageMonitor] CLI fetch failed:', error);
      return null;
    }
  }

  /**
   * Parse Claude CLI /usage command output
   * Example output:
   *   Session usage: 42% (resets in 3h 15m)
   *   Weekly usage: 78% (resets in 2d 5h)
   */
  private parseUsageOutput(
    output: string,
    profileId: string,
    profileName: string
  ): ClaudeUsageSnapshot | null {
    try {
      // Match session usage: "Session usage: 42%" or similar patterns
      const sessionMatch = output.match(/session\s+usage[:\s]+(\d+)%/i);
      const weeklyMatch = output.match(/weekly\s+usage[:\s]+(\d+)%/i);

      // Also try matching "5-hour" and "7-day" patterns
      const fiveHourMatch = output.match(/5-hour\s+usage[:\s]+(\d+)%/i);
      const sevenDayMatch = output.match(/7-day\s+usage[:\s]+(\d+)%/i);

      const sessionPercent = sessionMatch
        ? parseInt(sessionMatch[1], 10)
        : fiveHourMatch
        ? parseInt(fiveHourMatch[1], 10)
        : 0;

      const weeklyPercent = weeklyMatch
        ? parseInt(weeklyMatch[1], 10)
        : sevenDayMatch
        ? parseInt(sevenDayMatch[1], 10)
        : 0;

      // Try to extract reset times
      const sessionResetMatch = output.match(/session[^:]*:\s*\d+%\s*\(resets\s+in\s+([^)]+)\)/i);
      const weeklyResetMatch = output.match(/weekly[^:]*:\s*\d+%\s*\(resets\s+in\s+([^)]+)\)/i);
      const fiveHourResetMatch = output.match(/5-hour[^:]*:\s*\d+%\s*\(resets\s+in\s+([^)]+)\)/i);
      const sevenDayResetMatch = output.match(/7-day[^:]*:\s*\d+%\s*\(resets\s+in\s+([^)]+)\)/i);

      const sessionResetTime = sessionResetMatch?.[1] || fiveHourResetMatch?.[1] || undefined;
      const weeklyResetTime = weeklyResetMatch?.[1] || sevenDayResetMatch?.[1] || undefined;

      // Only return snapshot if we found at least one usage value
      if (sessionPercent > 0 || weeklyPercent > 0) {
        return {
          sessionPercent,
          weeklyPercent,
          sessionResetTime,
          weeklyResetTime,
          profileId,
          profileName,
          fetchedAt: new Date(),
          limitType: weeklyPercent > sessionPercent ? 'weekly' : 'session'
        };
      }

      return null;
    } catch (error) {
      console.error('[UsageMonitor] Failed to parse usage output:', error);
      return null;
    }
  }

  /**
   * Format ISO timestamp to human-readable reset time
   */
  private formatResetTime(isoTimestamp?: string): string {
    if (!isoTimestamp) return 'Unknown';

    try {
      const date = new Date(isoTimestamp);
      const now = new Date();
      const diffMs = date.getTime() - now.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (diffHours < 24) {
        return `${diffHours}h ${diffMins}m`;
      }

      const diffDays = Math.floor(diffHours / 24);
      const remainingHours = diffHours % 24;
      return `${diffDays}d ${remainingHours}h`;
    } catch (_error) {
      return isoTimestamp;
    }
  }

  /**
   * Perform proactive profile swap
   * @param currentProfileId - The profile to switch from
   * @param limitType - The type of limit that triggered the swap
   * @param additionalExclusions - Additional profile IDs to exclude (e.g., auth-failed profiles)
   */
  private async performProactiveSwap(
    currentProfileId: string,
    limitType: 'session' | 'weekly',
    additionalExclusions: string[] = []
  ): Promise<void> {
    const profileManager = getClaudeProfileManager();
    
    // Get all profiles to swap to, excluding current and any additional exclusions
    const allProfiles = profileManager.getProfilesSortedByAvailability();
    const excludeIds = new Set([currentProfileId, ...additionalExclusions]);
    const eligibleProfiles = allProfiles.filter(p => !excludeIds.has(p.id));
    
    if (eligibleProfiles.length === 0) {
      console.warn('[UsageMonitor] No alternative profile for proactive swap (excluded:', Array.from(excludeIds), ')');
      this.emit('proactive-swap-failed', {
        reason: additionalExclusions.length > 0 ? 'all_alternatives_failed_auth' : 'no_alternative',
        currentProfile: currentProfileId,
        excludedProfiles: Array.from(excludeIds)
      });
      return;
    }
    
    // Use the best available from eligible profiles
    const bestProfile = eligibleProfiles[0];

    console.warn('[UsageMonitor] Proactive swap:', {
      from: currentProfileId,
      to: bestProfile.id,
      reason: limitType
    });

    // Switch profile
    profileManager.setActiveProfile(bestProfile.id);

    // Emit swap event
    this.emit('proactive-swap-completed', {
      fromProfile: { id: currentProfileId, name: profileManager.getProfile(currentProfileId)?.name },
      toProfile: { id: bestProfile.id, name: bestProfile.name },
      limitType,
      timestamp: new Date()
    });

    // Notify UI
    this.emit('show-swap-notification', {
      fromProfile: profileManager.getProfile(currentProfileId)?.name,
      toProfile: bestProfile.name,
      reason: 'proactive',
      limitType
    });

    // Note: Don't immediately check new profile - let normal interval handle it
    // This prevents cascading swaps if multiple profiles are near limits
  }
}

/**
 * Get the singleton UsageMonitor instance
 */
export function getUsageMonitor(): UsageMonitor {
  return UsageMonitor.getInstance();
}
