import { ipcMain } from 'electron';
import { IPC_CHANNELS, getSpecsDir } from '../../../shared/constants';
import type { IPCResult, DecisionEntry, DecisionAuditTrail, DecisionAnnotationRequest } from '../../../shared/types';
import path from 'path';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { projectStore } from '../../project-store';

/**
 * Register decision audit trail handlers
 * Handles loading decisions from spec directory and annotating decisions
 */
export function registerDecisionHandlers(): void {
  /**
   * Get decision audit trail from spec directory
   * Returns decisions organized by phase with filtering capabilities
   */
  ipcMain.handle(
    IPC_CHANNELS.TASK_DECISIONS_GET,
    async (_, projectId: string, specId: string): Promise<IPCResult<DecisionAuditTrail | null>> => {
      try {
        const project = projectStore.getProject(projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const specsRelPath = getSpecsDir(project.autoBuildPath);
        const specDir = path.join(project.path, specsRelPath, specId);

        if (!existsSync(specDir)) {
          return { success: false, error: 'Spec directory not found' };
        }

        // Load decisions from decisions.json in the spec directory
        const decisionsPath = path.join(specDir, 'decisions.json');

        if (!existsSync(decisionsPath)) {
          // Return empty audit trail if no decisions file exists yet
          const emptyTrail: DecisionAuditTrail = {
            spec_id: specId,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            decisions: []
          };
          return { success: true, data: emptyTrail };
        }

        try {
          const content = readFileSync(decisionsPath, 'utf-8');
          const auditTrail: DecisionAuditTrail = JSON.parse(content);
          return { success: true, data: auditTrail };
        } catch (parseError) {
          console.error('Failed to parse decisions.json:', parseError);
          return {
            success: false,
            error: 'Failed to parse decisions file'
          };
        }
      } catch (error) {
        console.error('Failed to get task decisions:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get task decisions'
        };
      }
    }
  );

  /**
   * Annotate a decision (mark as good/bad pattern)
   * Updates the decision entry in decisions.json and optionally saves to Graphiti memory
   */
  ipcMain.handle(
    IPC_CHANNELS.TASK_DECISIONS_ANNOTATE,
    async (
      _,
      projectId: string,
      specId: string,
      request: DecisionAnnotationRequest
    ): Promise<IPCResult<DecisionEntry>> => {
      try {
        const project = projectStore.getProject(projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const specsRelPath = getSpecsDir(project.autoBuildPath);
        const specDir = path.join(project.path, specsRelPath, specId);

        if (!existsSync(specDir)) {
          return { success: false, error: 'Spec directory not found' };
        }

        const decisionsPath = path.join(specDir, 'decisions.json');

        if (!existsSync(decisionsPath)) {
          return { success: false, error: 'Decisions file not found' };
        }

        // Load current decisions
        const content = readFileSync(decisionsPath, 'utf-8');
        const auditTrail: DecisionAuditTrail = JSON.parse(content);

        // Find and update the decision
        const decisionIndex = auditTrail.decisions.findIndex(
          (d) => d.id === request.decision_id
        );

        if (decisionIndex === -1) {
          return { success: false, error: 'Decision not found' };
        }

        // Update the decision with annotation
        const updatedDecision: DecisionEntry = {
          ...auditTrail.decisions[decisionIndex],
          annotation: request.annotation,
          annotation_note: request.note
        };

        auditTrail.decisions[decisionIndex] = updatedDecision;
        auditTrail.updated_at = new Date().toISOString();

        // Save updated decisions
        writeFileSync(decisionsPath, JSON.stringify(auditTrail, null, 2));

        // TODO: If save_to_memory is true, save to Graphiti as pattern/gotcha
        // This will be implemented when Graphiti integration is added
        if (request.save_to_memory) {
          console.log(
            '[Decision Handler] save_to_memory requested - Graphiti integration not yet implemented'
          );
        }

        return { success: true, data: updatedDecision };
      } catch (error) {
        console.error('Failed to annotate decision:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to annotate decision'
        };
      }
    }
  );
}
