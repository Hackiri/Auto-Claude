import { FileText, Code } from 'lucide-react';
import matter from 'gray-matter';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { useTranslation } from 'react-i18next';
import type { Skill } from '../../../shared/types/skills';

interface SkillPreviewDialogProps {
  open: boolean;
  skill: Skill | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Dialog displaying a preview of the SKILL.md content
 * Shows YAML frontmatter and markdown instructions separately
 */
export function SkillPreviewDialog({
  open,
  skill,
  onOpenChange
}: SkillPreviewDialogProps) {
  const { t } = useTranslation(['skills', 'common']);

  // Generate SKILL.md content using gray-matter
  const skillContent = skill ? matter.stringify(skill.instructions, {
    name: skill.name,
    description: skill.description,
  }) : '';

  // Parse back to get frontmatter and instructions separately for display
  const { data: frontmatter, content: instructions } = skill
    ? matter(skillContent)
    : { data: {}, content: '' };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-purple-400" />
            {t('skills:preview.title')}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {skill?.name || ''}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex-1 overflow-auto min-h-0 -mx-6 px-6 space-y-4">
          {/* Frontmatter Section */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Code className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                {t('skills:preview.frontmatter')}
              </h3>
            </div>
            <pre className="text-xs bg-secondary/30 p-4 rounded-lg overflow-x-auto font-mono">
              <code className="text-muted-foreground">
                ---{'\n'}
                {Object.entries(frontmatter)
                  .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
                  .join('\n')}
                {'\n'}---
              </code>
            </pre>
          </div>

          {/* Instructions Section */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                {t('skills:preview.instructions')}
              </h3>
            </div>
            <div className="text-sm bg-secondary/30 p-4 rounded-lg overflow-x-auto">
              <pre className="whitespace-pre-wrap font-mono text-muted-foreground">
                {instructions}
              </pre>
            </div>
          </div>
        </div>

        <AlertDialogFooter className="mt-4">
          <AlertDialogCancel>{t('skills:preview.close')}</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
