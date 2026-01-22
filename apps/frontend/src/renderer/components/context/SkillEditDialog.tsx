/**
 * SkillEditDialog - Dialog for editing skill metadata (name and description)
 *
 * Features:
 * - Required fields: Name, Description
 * - Real-time validation with error display
 * - Name: max 64 chars, lowercase/numbers/hyphens only, no reserved words
 * - Description: max 1024 chars
 * - Save button updates skill in store
 * - Cancel button discards changes
 * - Save button disabled if validation fails
 */
import { useState, useEffect } from 'react';
import { Edit2 } from 'lucide-react';
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
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { useSkillsStore } from '../../stores/skills-store';
import { validateSkillName, validateSkillDescription } from '../../utils/skillValidation';
import type { Skill } from '../../../shared/types/skills';

interface SkillEditDialogProps {
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when the dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Skill to edit (null when dialog is closed) */
  skill: Skill | null;
}

export function SkillEditDialog({ open, onOpenChange, skill }: SkillEditDialogProps) {
  const { t } = useTranslation(['skills', 'common']);
  const { updateSkill } = useSkillsStore();

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  // Validation errors
  const [nameError, setNameError] = useState<string | null>(null);
  const [descriptionError, setDescriptionError] = useState<string | null>(null);

  // Reset form when dialog opens
  useEffect(() => {
    if (open && skill) {
      setName(skill.name);
      setDescription(skill.description);
      setNameError(null);
      setDescriptionError(null);
    }
  }, [open, skill]);

  // Real-time validation for name
  useEffect(() => {
    if (name === '') {
      setNameError(null);
      return;
    }
    const result = validateSkillName(name);
    if (!result.valid) {
      setNameError(result.error || t('skills:validation.nameRequired'));
    } else {
      setNameError(null);
    }
  }, [name, t]);

  // Real-time validation for description
  useEffect(() => {
    if (description === '') {
      setDescriptionError(null);
      return;
    }
    const result = validateSkillDescription(description);
    if (!result.valid) {
      setDescriptionError(result.error || t('skills:validation.descriptionRequired'));
    } else {
      setDescriptionError(null);
    }
  }, [description, t]);

  // Validate form
  const validateForm = (): boolean => {
    let isValid = true;

    // Name validation
    const nameResult = validateSkillName(name);
    if (!nameResult.valid) {
      setNameError(nameResult.error || t('skills:validation.nameRequired'));
      isValid = false;
    }

    // Description validation
    const descriptionResult = validateSkillDescription(description);
    if (!descriptionResult.valid) {
      setDescriptionError(descriptionResult.error || t('skills:validation.descriptionRequired'));
      isValid = false;
    }

    return isValid;
  };

  // Handle save
  const handleSave = () => {
    if (!validateForm() || !skill) {
      return;
    }

    // Update skill in store
    updateSkill(skill.id, {
      name: name.trim(),
      description: description.trim()
    });

    // Close dialog
    onOpenChange(false);
  };

  // Check if save button should be disabled
  const isSaveDisabled = !name.trim() || !description.trim() || !!nameError || !!descriptionError;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[min(92vw,600px)] max-h-[90vh] overflow-y-auto"
        data-testid="skill-edit-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit2 className="h-5 w-5 text-purple-400" />
            {t('skills:edit.title')}
          </DialogTitle>
          <DialogDescription>
            {skill?.name || ''}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Name field (required) */}
          <div className="space-y-2">
            <Label htmlFor="skill-name">
              {t('skills:edit.name')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="skill-name"
              placeholder={t('skills:edit.namePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={nameError ? 'border-destructive' : ''}
            />
            {nameError && <p className="text-sm text-destructive">{nameError}</p>}
            <p className="text-xs text-muted-foreground">
              {t('skills:validation.nameInvalidChars')}
            </p>
          </div>

          {/* Description field (required) */}
          <div className="space-y-2">
            <Label htmlFor="skill-description">
              {t('skills:edit.description')} <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="skill-description"
              placeholder={t('skills:edit.descriptionPlaceholder')}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={descriptionError ? 'border-destructive' : ''}
              rows={4}
            />
            {descriptionError && <p className="text-sm text-destructive">{descriptionError}</p>}
            <p className="text-xs text-muted-foreground">
              {t('skills:edit.characterCount', { count: description.length, max: 1024 })}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {t('skills:edit.cancel')}
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={isSaveDisabled}
          >
            {t('skills:edit.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
