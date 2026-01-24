import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  AlertCircle,
  Sparkles,
  Wand2,
  Server,
  Database,
  Globe,
  Workflow,
  CheckCircle2,
  StopCircle,
  Brain
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { Progress } from '../ui/progress';
import { cn } from '../../lib/utils';
import { SkillCard } from './SkillCard';
import { SkillPreviewDialog } from './SkillPreviewDialog';
import { SkillEditDialog } from './SkillEditDialog';
import { SkillGenerateDialog } from './SkillGenerateDialog';
import { useSkillsStore, exportSingleSkill, loadSkills, exportSkills } from '../../stores/skills-store';
// Note: useContextStore no longer needed - AI analyzes project directly without projectIndex
import { useTranslation } from 'react-i18next';
import { skillFilterCategories } from './constants';
import type { Skill } from '../../../shared/types/skills';
import type { SkillsProgressData, GeneratedSkill } from '../../../preload/api/skills-api';
import { v4 as uuidv4 } from 'uuid';

type FilterCategory = keyof typeof skillFilterCategories;

interface SkillsTabProps {
  projectId: string;
}

// Filter icons for each category
const filterIcons: Record<FilterCategory, React.ElementType> = {
  all: Sparkles,
  ai: Brain,
  service: Server,
  database: Database,
  api: Globe,
  ci: Workflow,
  enabled: CheckCircle2
};

export function SkillsTab({ projectId }: SkillsTabProps) {
  const { t } = useTranslation(['skills', 'common']);
  // Note: No longer requiring projectIndex - AI analyzes project directly
  const {
    skills,
    skillsLoading,
    skillsError,
    generationLoading,
    generationError,
    setSkills,
    setGenerationLoading,
    setGenerationError,
    toggleSkill,
  } = useSkillsStore();

  // Dialog states
  const [previewSkill, setPreviewSkill] = useState<Skill | null>(null);
  const [editSkill, setEditSkill] = useState<Skill | null>(null);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FilterCategory>('all');

  // AI generation state
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiProgress, setAiProgress] = useState<SkillsProgressData | null>(null);

  // Calculate skill counts by category
  const skillCounts = useMemo(() => {
    const counts: Record<FilterCategory, number> = {
      all: skills.length,
      ai: 0,
      service: 0,
      database: 0,
      api: 0,
      ci: 0,
      enabled: 0
    };

    for (const skill of skills) {
      if (skill.source in counts) {
        counts[skill.source as FilterCategory]++;
      }
      if (skill.enabled) {
        counts.enabled++;
      }
    }

    return counts;
  }, [skills]);

  // Filter skills based on active filter
  const filteredSkills = useMemo(() => {
    if (activeFilter === 'all') return skills;
    if (activeFilter === 'enabled') return skills.filter(s => s.enabled);
    return skills.filter(skill => skill.source === activeFilter);
  }, [skills, activeFilter]);

  // Load skills from disk on mount and when projectId changes
  useEffect(() => {
    if (projectId) {
      loadSkills(projectId);
    }
  }, [projectId]);

  // Register AI generation event listeners
  useEffect(() => {
    // Check if electronAPI and AI skills methods are available
    if (!window.electronAPI?.onSkillsAIProgress) return;

    const unsubProgress = window.electronAPI.onSkillsAIProgress((pid, status) => {
      if (pid === projectId) {
        setAiProgress(status);
      }
    });

    const unsubComplete = window.electronAPI.onSkillsAIComplete(async (pid, generatedSkills) => {
      if (pid === projectId) {
        // Convert generated skills to Skill format
        const convertedSkills: Skill[] = generatedSkills.map((gs: GeneratedSkill) => ({
          id: uuidv4(),
          name: gs.name,
          description: gs.description,
          instructions: gs.instructions,
          enabled: true,
          source: 'ai' as const,
          metadata: {
            generatedFrom: 'ai',
            generatedAt: new Date().toISOString()
          }
        }));
        setSkills(convertedSkills);

        // Auto-export all generated skills to disk for persistence
        try {
          for (const skill of convertedSkills) {
            await window.electronAPI.exportSkill(projectId, skill);
          }
          console.log(`[SkillsTab] Auto-exported ${convertedSkills.length} skills to disk`);
        } catch (err) {
          console.warn('[SkillsTab] Failed to auto-export skills:', err);
        }

        setAiGenerating(false);
        setAiProgress(null);
        setGenerationError(null);
      }
    });

    const unsubError = window.electronAPI.onSkillsAIError((pid, error) => {
      if (pid === projectId) {
        setGenerationError(error);
        setAiGenerating(false);
        setAiProgress(null);
      }
    });

    const unsubStopped = window.electronAPI.onSkillsAIStopped((pid) => {
      if (pid === projectId) {
        setAiGenerating(false);
        setAiProgress(null);
      }
    });

    return () => {
      unsubProgress();
      unsubComplete();
      unsubError();
      unsubStopped();
    };
  }, [projectId, setSkills, setGenerationError]);

  // AI-powered skills generation
  const handleAIGenerate = useCallback(() => {
    console.log('[SkillsTab] handleAIGenerate called, electronAPI:', !!window.electronAPI, 'generateSkillsAI:', !!window.electronAPI?.generateSkillsAI);
    // Check if electronAPI and the generateSkillsAI method exist
    if (!window.electronAPI?.generateSkillsAI) {
      const errorMsg = `[FIXED-v4-${Date.now()}] electronAPI.generateSkillsAI not available`;
      console.error('[SkillsTab] API check failed:', errorMsg);
      setGenerationError(errorMsg);
      return;
    }
    console.log('[SkillsTab] API check passed, starting generation');

    setAiGenerating(true);
    setGenerationError(null);
    setAiProgress({ phase: 'starting', progress: 0, message: t('skills:aiGenerate.starting') });

    window.electronAPI.generateSkillsAI(projectId, {
      model: 'sonnet',
      thinkingLevel: 'medium',
      maxSkills: 8
    }, false);
  }, [projectId, setGenerationError, t]);

  // Stop AI generation
  const handleStopAI = useCallback(async () => {
    if (!window.electronAPI?.stopSkillsAI) return;
    await window.electronAPI.stopSkillsAI(projectId);
  }, [projectId]);

  // Handle skill export
  const handleExport = async (skill: Skill) => {
    const success = await exportSingleSkill(projectId, skill);
    if (success) {
      console.log(t('skills:export.success'));
    }
  };

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6">
        {/* Header with actions */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{t('skills:title')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('skills:description', { defaultValue: 'Claude Code skills for your project' })}
            </p>
          </div>
          <div className="flex gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowGenerateDialog(true)}
                  disabled={aiGenerating}
                >
                  <Wand2 className="h-4 w-4 mr-2" />
                  {t('skills:generateFromPrompt')}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t('skills:promptGenerate.description')}
              </TooltipContent>
            </Tooltip>
            {aiGenerating ? (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleStopAI}
              >
                <StopCircle className="h-4 w-4 mr-2" />
                {t('skills:aiGenerate.stop', { defaultValue: 'Stop' })}
              </Button>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="sm"
                    onClick={handleAIGenerate}
                    disabled={generationLoading || aiGenerating}
                  >
                    <Brain className="h-4 w-4 mr-2" />
                    {t('skills:aiGenerate.button', { defaultValue: 'Analyze & Generate' })}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t('skills:aiGenerate.tooltip', { defaultValue: 'Use AI to analyze project and generate contextual skills' })}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>

        {/* AI Generation Progress */}
        {aiGenerating && aiProgress && (
          <Card className="border-primary/50 bg-primary/5">
            <CardContent className="pt-4">
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <Brain className="h-5 w-5 text-primary animate-pulse" />
                  <div className="flex-1">
                    <p className="font-medium text-sm">
                      {t('skills:aiGenerate.inProgress', { defaultValue: 'Analyzing project architecture...' })}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {aiProgress.message || aiProgress.phase}
                    </p>
                  </div>
                  <span className="text-sm font-medium text-primary">
                    {aiProgress.progress}%
                  </span>
                </div>
                <Progress value={aiProgress.progress} className="h-2" />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error state */}
        {(skillsError || generationError) && !aiGenerating && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">{t('skills:generate.error')}</p>
              <p className="text-sm opacity-80">{skillsError || generationError}</p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {(skillsLoading || generationLoading) && skills.length === 0 && !aiGenerating && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty state */}
        {!skillsLoading && !generationLoading && !aiGenerating && skills.length === 0 && !skillsError && !generationError && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Brain className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground">{t('skills:empty.title')}</h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-sm">
              {t('skills:empty.aiDescription', { defaultValue: 'AI can analyze your project architecture and generate contextual skills that help Claude work effectively with your codebase.' })}
            </p>
            <div className="flex gap-3 mt-4">
              <Button
                variant="outline"
                onClick={() => setShowGenerateDialog(true)}
              >
                <Wand2 className="h-4 w-4 mr-2" />
                {t('skills:generateFromPrompt')}
              </Button>
              <Button onClick={handleAIGenerate} disabled={generationLoading || aiGenerating}>
                <Brain className="h-4 w-4 mr-2" />
                {t('skills:aiGenerate.button', { defaultValue: 'Analyze & Generate' })}
              </Button>
            </div>
          </div>
        )}

        {/* Skills content */}
        {skills.length > 0 && (
          <div className="space-y-6">
            {/* Stats Summary Card */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  {t('skills:statsTitle', { defaultValue: 'Skills Overview' })}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 sm:grid-cols-7 gap-2">
                  <div className="text-center p-2 rounded-lg bg-muted/30">
                    <div className="text-lg font-semibold text-foreground">{skillCounts.all}</div>
                    <div className="text-xs text-muted-foreground">Total</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-cyan-500/10">
                    <div className="text-lg font-semibold text-cyan-400">{skillCounts.ai}</div>
                    <div className="text-xs text-muted-foreground">AI</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-blue-500/10">
                    <div className="text-lg font-semibold text-blue-400">{skillCounts.service}</div>
                    <div className="text-xs text-muted-foreground">Services</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-green-500/10">
                    <div className="text-lg font-semibold text-green-400">{skillCounts.database}</div>
                    <div className="text-xs text-muted-foreground">Database</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-purple-500/10">
                    <div className="text-lg font-semibold text-purple-400">{skillCounts.api}</div>
                    <div className="text-xs text-muted-foreground">API</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-amber-500/10">
                    <div className="text-lg font-semibold text-amber-400">{skillCounts.ci}</div>
                    <div className="text-xs text-muted-foreground">CI/CD</div>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-emerald-500/10">
                    <div className="text-lg font-semibold text-emerald-400">{skillCounts.enabled}</div>
                    <div className="text-xs text-muted-foreground">Enabled</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Skills Browser Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  {t('skills:browserTitle', { defaultValue: 'Skills Browser' })}
                </h3>
                <span className="text-xs text-muted-foreground">
                  {filteredSkills.length} of {skills.length} skills
                </span>
              </div>

              {/* Filter Pills */}
              <div className="flex flex-wrap gap-2">
                {(Object.keys(skillFilterCategories) as FilterCategory[]).map((category) => {
                  const config = skillFilterCategories[category];
                  const count = skillCounts[category];
                  const Icon = filterIcons[category];
                  const isActive = activeFilter === category;

                  return (
                    <Button
                      key={category}
                      variant={isActive ? 'default' : 'outline'}
                      size="sm"
                      className={cn(
                        'gap-1.5 h-8',
                        isActive && 'bg-accent text-accent-foreground',
                        !isActive && count === 0 && 'opacity-50'
                      )}
                      onClick={() => setActiveFilter(category)}
                      disabled={count === 0 && category !== 'all'}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      <span>{config.label}</span>
                      {count > 0 && (
                        <Badge
                          variant="secondary"
                          className={cn(
                            'ml-1 px-1.5 py-0 text-xs',
                            isActive && 'bg-background/20'
                          )}
                        >
                          {count}
                        </Badge>
                      )}
                    </Button>
                  );
                })}
              </div>

              {/* No results for filter */}
              {filteredSkills.length === 0 && skills.length > 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Sparkles className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">
                    {t('skills:noFilterResults', { defaultValue: 'No skills match the selected filter.' })}
                  </p>
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => setActiveFilter('all')}
                    className="mt-2"
                  >
                    {t('skills:showAll', { defaultValue: 'Show all skills' })}
                  </Button>
                </div>
              )}

              {/* Skills List */}
              {filteredSkills.length > 0 && (
                <div className="space-y-3">
                  {filteredSkills.map((skill) => (
                    <SkillCard
                      key={skill.id}
                      skill={skill}
                      onToggle={toggleSkill}
                      onPreview={setPreviewSkill}
                      onEdit={setEditSkill}
                      onExport={handleExport}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Preview Dialog */}
      <SkillPreviewDialog
        open={!!previewSkill}
        skill={previewSkill}
        onOpenChange={(open) => !open && setPreviewSkill(null)}
      />

      {/* Edit Dialog */}
      <SkillEditDialog
        open={!!editSkill}
        skill={editSkill}
        onOpenChange={(open) => !open && setEditSkill(null)}
      />

      {/* Generate from Prompt Dialog */}
      <SkillGenerateDialog
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
        projectId={projectId}
      />
    </ScrollArea>
  );
}
