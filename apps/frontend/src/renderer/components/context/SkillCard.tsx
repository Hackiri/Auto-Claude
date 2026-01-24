import { Eye, Edit, Download } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { cn } from '../../lib/utils';
import type { Skill } from '../../../shared/types/skills';
import { skillSourceIcons, skillSourceColors } from './constants';
import { useTranslation } from 'react-i18next';

interface SkillCardProps {
  skill: Skill;
  onToggle: (id: string) => void;
  onPreview: (skill: Skill) => void;
  onEdit: (skill: Skill) => void;
  onExport: (skill: Skill) => void;
}

export function SkillCard({ skill, onToggle, onPreview, onEdit, onExport }: SkillCardProps) {
  const { t } = useTranslation(['skills', 'common']);
  const Icon = skillSourceIcons[skill.source] || skillSourceIcons['unknown'];
  const colorClass = skillSourceColors[skill.source] || skillSourceColors['unknown'];

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Icon className="h-4 w-4" />
            {skill.name}
          </CardTitle>
          <Badge variant="outline" className={cn('capitalize text-xs', colorClass)}>
            {skill.source}
          </Badge>
        </div>
        <CardDescription className="text-xs line-clamp-2">
          {skill.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground">
            {skill.enabled ? t('skills:card.enabled') : t('skills:card.disabled')}
          </span>
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <Switch
                  checked={skill.enabled}
                  onCheckedChange={() => onToggle(skill.id)}
                  aria-label={skill.enabled ? t('skills:card.disable') : t('skills:card.enable')}
                />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              {skill.enabled ? t('skills:card.disableTooltip') : t('skills:card.enableTooltip')}
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onPreview(skill)}
              >
                <Eye className="h-3 w-3 mr-1.5" />
                {t('skills:card.preview')}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('skills:card.previewTooltip')}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onEdit(skill)}
              >
                <Edit className="h-3 w-3 mr-1.5" />
                {t('skills:card.edit')}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('skills:card.editTooltip')}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onExport(skill)}
                disabled={!skill.enabled}
              >
                <Download className="h-3 w-3 mr-1.5" />
                {t('skills:card.export')}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {skill.enabled
                ? t('skills:card.exportTooltip')
                : t('skills:card.exportDisabledTooltip')}
            </TooltipContent>
          </Tooltip>
        </div>
      </CardContent>
    </Card>
  );
}
