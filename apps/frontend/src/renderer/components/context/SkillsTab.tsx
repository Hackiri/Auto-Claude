import { useState } from 'react';
import { RefreshCw, AlertCircle, Sparkles, Wand2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { cn } from '../../lib/utils';
import { SkillCard } from './SkillCard';
import { SkillPreviewDialog } from './SkillPreviewDialog';
import { SkillEditDialog } from './SkillEditDialog';
import { SkillGenerateDialog } from './SkillGenerateDialog';
import { useSkillsStore, exportSingleSkill } from '../../stores/skills-store';
import { generateSkillsFromProjectIndex } from '../../../shared/utils/skillGenerator';
import { useContextStore } from '../../stores/context-store';
import { useTranslation } from 'react-i18next';
import type { Skill } from '../../../shared/types/skills';

interface SkillsTabProps {
  projectId: string;
}

export function SkillsTab({ projectId }: SkillsTabProps) {
  const { t } = useTranslation(['skills', 'common']);
  const { projectIndex } = useContextStore();
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

  // Auto-generate skills from project index
  const handleAutoGenerate = () => {
    if (!projectIndex) {
      setGenerationError(t('skills:generate.noData'));
      return;
    }

    setGenerationLoading(true);
    setGenerationError(null);

    try {
      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: true,
        includeDatabases: true,
        includeApis: true,
        includeCiWorkflows: true,
        autoEnable: false,
      });

      if (result.success) {
        setSkills(result.skills);
      } else {
        setGenerationError(
          result.errors?.map((e) => e.error).join(', ') || t('skills:generate.error')
        );
      }
    } catch (error) {
      setGenerationError(error instanceof Error ? error.message : t('skills:generate.error'));
    } finally {
      setGenerationLoading(false);
    }
  };

  // Handle skill export
  const handleExport = async (skill: Skill) => {
    const success = await exportSingleSkill(projectId, skill);
    if (success) {
      // Show success notification (could use toast here)
      console.log(t('skills:export.success'));
    }
  };

  // Count enabled skills
  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6">
        {/* Header with auto-generate and prompt generate buttons */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{t('skills:title')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('skills:generate.success', { count: skills.length })}
              {enabledCount > 0 && (
                <>
                  {' • '}
                  <Badge variant="secondary" className="text-xs">
                    {t('skills:enabledCount', { count: enabledCount })}
                  </Badge>
                </>
              )}
            </p>
          </div>
          <div className="flex gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowGenerateDialog(true)}
                >
                  <Wand2 className="h-4 w-4 mr-2" />
                  {t('skills:generateFromPrompt')}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t('skills:promptGenerate.description')}
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAutoGenerate}
                  disabled={generationLoading || !projectIndex}
                >
                  <RefreshCw
                    className={cn('h-4 w-4 mr-2', generationLoading && 'animate-spin')}
                  />
                  {t('skills:autoGenerate')}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t('skills:autoGenerate')}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Error state */}
        {(skillsError || generationError) && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">{t('skills:generate.error')}</p>
              <p className="text-sm opacity-80">{skillsError || generationError}</p>
            </div>
          </div>
        )}

        {/* Loading state */}
        {(skillsLoading || generationLoading) && skills.length === 0 && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty state */}
        {!skillsLoading && !generationLoading && skills.length === 0 && !skillsError && !generationError && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Sparkles className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground">{t('skills:empty.title')}</h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-sm">
              {t('skills:empty.description')}
            </p>
            <div className="flex gap-3 mt-4">
              <Button
                variant="outline"
                onClick={() => setShowGenerateDialog(true)}
              >
                <Wand2 className="h-4 w-4 mr-2" />
                {t('skills:generateFromPrompt')}
              </Button>
              <Button onClick={handleAutoGenerate} disabled={!projectIndex}>
                <Sparkles className="h-4 w-4 mr-2" />
                {t('skills:empty.action')}
              </Button>
            </div>
          </div>
        )}

        {/* Skills grid */}
        {skills.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {skills.map((skill) => (
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
