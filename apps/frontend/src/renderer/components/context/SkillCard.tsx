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
      <CardHeader className="p-4 pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2 truncate">
            <Icon className="h-4 w-4 shrink-0" />
            <span className="truncate">{skill.name}</span>
          </CardTitle>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant="outline" className={cn('capitalize text-xs', colorClass)}>
              {skill.source}
            </Badge>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Switch
                    checked={skill.enabled}
                    onCheckedChange={() => onToggle(skill.id)}
                    aria-label={skill.enabled ? t('skills:card.disable') : t('skills:card.enable')}
                    className="scale-90"
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent>
                {skill.enabled ? t('skills:card.disableTooltip') : t('skills:card.enableTooltip')}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
        <CardDescription className="text-xs line-clamp-2 mt-1">
          {skill.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 pt-2">
        {/* Action Buttons - Icon only */}
        <div className="flex gap-1.5 justify-end">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onPreview(skill)}
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('skills:card.previewTooltip')}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onEdit(skill)}
              >
                <Edit className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('skills:card.editTooltip')}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onExport(skill)}
                disabled={!skill.enabled}
              >
                <Download className="h-3.5 w-3.5" />
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
