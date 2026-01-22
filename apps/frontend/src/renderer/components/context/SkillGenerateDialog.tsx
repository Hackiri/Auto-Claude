/**
 * SkillGenerateDialog - Dialog for generating a skill from a natural language prompt
 *
 * Features:
 * - Text area for entering a prompt describing the skill
 * - Real-time validation
 * - Generate button triggers AI-based skill generation
 * - Loading state while generating
 * - Cancel button closes dialog
 */
import { useState, useEffect } from 'react';
import { Sparkles, Loader2, Wand2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Input } from '../ui/input';
import { useSkillsStore } from '../../stores/skills-store';
import type { Skill, SkillSource } from '../../../shared/types/skills';

interface SkillGenerateDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when the dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Project ID for skill generation */
  projectId: string;
  /** Callback when a skill is successfully generated */
  onSkillGenerated?: (skill: Skill) => void;
}

const MAX_PROMPT_LENGTH = 2000;
const MAX_NAME_LENGTH = 64;

export function SkillGenerateDialog({
  open,
  onOpenChange,
  projectId,
  onSkillGenerated
}: SkillGenerateDialogProps) {
  const { t } = useTranslation(['skills', 'common']);
  const { addSkill } = useSkillsStore();

  // Form state
  const [prompt, setPrompt] = useState('');
  const [skillName, setSkillName] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setPrompt('');
      setSkillName('');
      setError(null);
      setIsGenerating(false);
    }
  }, [open]);

  // Validate prompt
  const isPromptValid = prompt.trim().length >= 10 && prompt.length <= MAX_PROMPT_LENGTH;
  const isNameValid = skillName.trim().length > 0 && skillName.length <= MAX_NAME_LENGTH && /^[a-z0-9-]+$/.test(skillName);

  // Check if generate button should be disabled
  const isGenerateDisabled = !isPromptValid || !isNameValid || isGenerating;

  // Handle generate
  const handleGenerate = async () => {
    if (isGenerateDisabled) return;

    setIsGenerating(true);
    setError(null);

    try {
      // Call IPC to generate skill from prompt
      const result = await window.electronAPI.generateSkillFromPrompt(
        projectId,
        skillName.trim(),
        prompt.trim()
      );

      if (result.success && result.data) {
        // Add the generated skill to the store
        addSkill(result.data);

        // Notify parent
        if (onSkillGenerated) {
          onSkillGenerated(result.data);
        }

        // Close dialog
        onOpenChange(false);
      } else {
        setError(result.error || t('skills:promptGenerate.error'));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('skills:promptGenerate.error'));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[min(92vw,600px)] max-h-[90vh] overflow-y-auto"
        data-testid="skill-generate-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-purple-400" />
            {t('skills:promptGenerate.title')}
          </DialogTitle>
          <DialogDescription>
            {t('skills:promptGenerate.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Error alert */}
          {error && (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}

          {/* Skill name field */}
          <div className="space-y-2">
            <Label htmlFor="skill-generate-name">
              {t('skills:promptGenerate.name')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="skill-generate-name"
              placeholder={t('skills:promptGenerate.namePlaceholder')}
              value={skillName}
              onChange={(e) => setSkillName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              disabled={isGenerating}
              maxLength={MAX_NAME_LENGTH}
            />
            <p className="text-xs text-muted-foreground">
              {t('skills:validation.nameInvalidChars')}
            </p>
          </div>

          {/* Prompt field */}
          <div className="space-y-2">
            <Label htmlFor="skill-generate-prompt">
              {t('skills:promptGenerate.prompt')} <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="skill-generate-prompt"
              placeholder={t('skills:promptGenerate.promptPlaceholder')}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isGenerating}
              rows={6}
              maxLength={MAX_PROMPT_LENGTH}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{t('skills:promptGenerate.promptHint')}</span>
              <span>
                {t('skills:edit.characterCount', { count: prompt.length, max: MAX_PROMPT_LENGTH })}
              </span>
            </div>
          </div>

          {/* Example prompts */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">
              {t('skills:promptGenerate.examples')}
            </p>
            <div className="space-y-1">
              <button
                type="button"
                className="w-full text-left text-xs p-2 rounded bg-secondary/50 hover:bg-secondary/80 transition-colors"
                onClick={() => {
                  setSkillName('react-component');
                  setPrompt('Create a skill that helps build React components with TypeScript, proper prop types, and follows the project\'s coding conventions. Include guidance on state management patterns used in this project.');
                }}
                disabled={isGenerating}
              >
                <Sparkles className="h-3 w-3 inline mr-1.5" />
                {t('skills:promptGenerate.exampleReact')}
              </button>
              <button
                type="button"
                className="w-full text-left text-xs p-2 rounded bg-secondary/50 hover:bg-secondary/80 transition-colors"
                onClick={() => {
                  setSkillName('api-endpoint');
                  setPrompt('Create a skill for building REST API endpoints with proper error handling, validation, authentication checks, and following the existing API patterns in this codebase.');
                }}
                disabled={isGenerating}
              >
                <Sparkles className="h-3 w-3 inline mr-1.5" />
                {t('skills:promptGenerate.exampleApi')}
              </button>
              <button
                type="button"
                className="w-full text-left text-xs p-2 rounded bg-secondary/50 hover:bg-secondary/80 transition-colors"
                onClick={() => {
                  setSkillName('test-writing');
                  setPrompt('Create a skill for writing unit tests and integration tests using the testing framework in this project. Include patterns for mocking, test data setup, and assertion best practices.');
                }}
                disabled={isGenerating}
              >
                <Sparkles className="h-3 w-3 inline mr-1.5" />
                {t('skills:promptGenerate.exampleTest')}
              </button>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isGenerating}
          >
            {t('skills:edit.cancel')}
          </Button>
          <Button
            type="button"
            onClick={handleGenerate}
            disabled={isGenerateDisabled}
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {t('skills:promptGenerate.generating')}
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4 mr-2" />
                {t('skills:promptGenerate.generate')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
