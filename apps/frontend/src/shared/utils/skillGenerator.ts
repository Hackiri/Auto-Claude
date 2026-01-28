/**
 * Skill generation utilities for auto-generating Claude Agent Skills from project index
 */

import type { ProjectIndex, ServiceInfo } from '../types/project';
import type {
  Skill,
  SkillGenerationOptions,
  SkillGenerationResult,
} from '../types/skills';

/**
 * Sanitize a string to be used as a skill name
 * - Converts to lowercase
 * - Replaces spaces and special characters with hyphens
 * - Removes consecutive hyphens
 * - Trims leading/trailing hyphens
 */
function sanitizeSkillName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-') // Replace non-alphanumeric with hyphens
    .replace(/-+/g, '-') // Replace consecutive hyphens with single hyphen
    .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
}

/**
 * Generate a unique skill ID
 */
function generateSkillId(source: string, name: string): string {
  return `${source}-${sanitizeSkillName(name)}-${Date.now()}`;
}

/**
 * Ensure skill name is unique by appending a numeric suffix if needed
 */
function ensureUniqueName(name: string, existingNames: Set<string>): string {
  let uniqueName = name;
  let counter = 1;

  while (existingNames.has(uniqueName)) {
    uniqueName = `${name}-${counter}`;
    counter++;
  }

  existingNames.add(uniqueName);
  return uniqueName;
}

/**
 * Generate a skill from a service
 */
function generateServiceSkill(
  serviceName: string,
  service: ServiceInfo,
  existingNames: Set<string>,
  autoEnable: boolean,
): Skill {
  const baseName = sanitizeSkillName(`service-${serviceName}`);
  const name = ensureUniqueName(baseName, existingNames);

  const languageInfo = service.language ? ` (${service.language}` : '';
  const frameworkInfo = service.framework ? `/${service.framework})` : languageInfo ? ')' : '';
  const typeInfo = service.type ? ` ${service.type}` : '';

  const description = `Interact with ${serviceName}${typeInfo} service${languageInfo}${frameworkInfo}`;

  const instructions = `## Purpose

This skill helps you work with the ${serviceName} service in the project.

${service.type ? `**Service Type:** ${service.type}\n` : ''}${service.language ? `**Language:** ${service.language}\n` : ''}${service.framework ? `**Framework:** ${service.framework}\n` : ''}${service.package_manager ? `**Package Manager:** ${service.package_manager}\n` : ''}${service.default_port ? `**Default Port:** ${service.default_port}\n` : ''}

## Usage

Use this skill when you need to:
- Understand the ${serviceName} service architecture
- Modify or add features to ${serviceName}
- Debug issues in the ${serviceName} service
- Review or refactor ${serviceName} code

## Service Location

**Path:** \`${service.path}\`
${service.entry_point ? `**Entry Point:** \`${service.entry_point}\`\n` : ''}
## Key Directories

${
  service.key_directories
    ? Object.entries(service.key_directories)
        .map(([dirName, dirInfo]) => `- **${dirName}**: ${dirInfo.purpose} (\`${dirInfo.path}\`)`)
        .join('\n')
    : 'No key directories specified.'
}

${
  service.dependencies && service.dependencies.length > 0
    ? `## Dependencies\n\n${service.dependencies.slice(0, 10).map((dep) => `- ${dep}`).join('\n')}${service.dependencies.length > 10 ? `\n- ...and ${service.dependencies.length - 10} more` : ''}\n`
    : ''
}
${service.testing ? `## Testing\n\n**Framework:** ${service.testing}\n${service.test_directory ? `**Test Directory:** \`${service.test_directory}\`\n` : ''}\n` : ''}
## Examples

\`\`\`
# When working on the ${serviceName} service:
"Add a new feature to ${serviceName}"
"Debug the authentication flow in ${serviceName}"
"Refactor the ${service.key_directories ? Object.keys(service.key_directories)[0] : 'core'} module"
\`\`\`
`;

  return {
    id: generateSkillId('service', serviceName),
    name,
    description,
    enabled: autoEnable,
    source: 'service',
    metadata: {
      serviceName,
      language: service.language,
      framework: service.framework,
      type: service.type,
      path: service.path,
    },
    instructions,
  };
}

/**
 * Generate a skill from a database model
 */
function generateDatabaseSkill(
  serviceName: string,
  modelName: string,
  modelInfo: {
    orm?: string;
    fields: Record<string, unknown>;
    table?: string;
  },
  existingNames: Set<string>,
  autoEnable: boolean,
): Skill {
  const baseName = sanitizeSkillName(`db-model-${modelName}`);
  const name = ensureUniqueName(baseName, existingNames);

  const ormInfo = modelInfo.orm ? ` using ${modelInfo.orm}` : '';
  const description = `Query and manipulate ${modelName} database model${ormInfo}`;

  const fieldsList = Object.entries(modelInfo.fields || {})
    .slice(0, 10)
    .map(([fieldName, fieldInfo]) => {
      const info = fieldInfo as { type?: string; primary_key?: boolean };
      const typeStr = info.type || 'Unknown';
      const pkStr = info.primary_key ? ' (Primary Key)' : '';
      return `- **${fieldName}**: ${typeStr}${pkStr}`;
    })
    .join('\n');

  const instructions = `## Purpose

This skill helps you work with the ${modelName} database model.

${modelInfo.orm ? `**ORM:** ${modelInfo.orm}\n` : ''}${modelInfo.table ? `**Table:** \`${modelInfo.table}\`\n` : ''}**Service:** ${serviceName}

## Schema

${fieldsList || 'No field information available.'}
${Object.keys(modelInfo.fields || {}).length > 10 ? `\n...and ${Object.keys(modelInfo.fields).length - 10} more fields` : ''}

## Usage

Use this skill when you need to:
- Query ${modelName} records
- Create, update, or delete ${modelName} entries
- Understand the ${modelName} schema
- Add migrations or modify the ${modelName} model

## Examples

\`\`\`
# When working with ${modelName}:
"Add a new field to ${modelName}"
"Query all ${modelName} records with a specific condition"
"Create a migration to modify ${modelName}"
\`\`\`
`;

  return {
    id: generateSkillId('database', modelName),
    name,
    description,
    enabled: autoEnable,
    source: 'database',
    metadata: {
      serviceName,
      modelName,
      orm: modelInfo.orm,
      table: modelInfo.table,
      fieldCount: Object.keys(modelInfo.fields || {}).length,
    },
    instructions,
  };
}

/**
 * Generate a skill from an API route
 */
function generateApiSkill(
  serviceName: string,
  route: {
    path: string;
    methods: string[];
    framework?: string;
    requires_auth?: boolean;
  },
  existingNames: Set<string>,
  autoEnable: boolean,
): Skill {
  const methodsStr = route.methods.join('-').toLowerCase();
  const pathSanitized = route.path.replace(/^\//, '').replace(/\//g, '-') || 'root';
  const baseName = sanitizeSkillName(`api-${methodsStr}-${pathSanitized}`);
  const name = ensureUniqueName(baseName, existingNames);

  const frameworkInfo = route.framework ? ` (${route.framework})` : '';
  const description = `Call ${route.methods.join('/')} ${route.path} API endpoint${frameworkInfo}`;

  const instructions = `## Purpose

This skill helps you interact with the \`${route.path}\` API endpoint.

**Methods:** ${route.methods.join(', ')}
${route.framework ? `**Framework:** ${route.framework}\n` : ''}${route.requires_auth ? '**Authentication:** Required\n' : ''}**Service:** ${serviceName}

## Usage

Use this skill when you need to:
- Call the \`${route.path}\` endpoint
- Understand request/response format for \`${route.path}\`
- Debug or test the \`${route.path}\` endpoint
- Modify the \`${route.path}\` route implementation

## Endpoint Details

**Path:** \`${route.path}\`
**Methods:** ${route.methods.map((m) => `\`${m}\``).join(', ')}
${route.requires_auth ? '\n⚠️ **This endpoint requires authentication**\n' : ''}
## Examples

\`\`\`
# When working with this endpoint:
"Call ${route.methods[0]} ${route.path} with sample data"
"Add validation to the ${route.path} endpoint"
"Test the ${route.path} route"
\`\`\`
`;

  return {
    id: generateSkillId('api', `${methodsStr}-${pathSanitized}`),
    name,
    description,
    enabled: autoEnable,
    source: 'api',
    metadata: {
      serviceName,
      path: route.path,
      methods: route.methods,
      framework: route.framework,
      requiresAuth: route.requires_auth,
    },
    instructions,
  };
}

/**
 * Generate a skill from a CI/CD workflow
 */
function generateCiWorkflowSkill(
  workflowName: string,
  ciType: string,
  existingNames: Set<string>,
  autoEnable: boolean,
): Skill {
  const baseName = sanitizeSkillName(`ci-${workflowName.replace(/\.yml$/, '')}`);
  const name = ensureUniqueName(baseName, existingNames);

  const description = `Understand and modify ${workflowName} CI/CD workflow`;

  const instructions = `## Purpose

This skill helps you work with the ${workflowName} CI/CD workflow.

**CI System:** ${ciType}
**Workflow File:** \`${workflowName}\`

## Usage

Use this skill when you need to:
- Modify the ${workflowName} workflow
- Debug CI/CD pipeline issues in ${workflowName}
- Add new steps or jobs to ${workflowName}
- Understand what ${workflowName} does

## Workflow Details

**Name:** ${workflowName.replace(/\.yml$/, '').replace(/-/g, ' ')}
**Type:** ${ciType}

## Examples

\`\`\`
# When working with this workflow:
"Add a new test step to ${workflowName}"
"Fix the failing ${workflowName} workflow"
"Explain what ${workflowName} does"
\`\`\`
`;

  return {
    id: generateSkillId('ci', workflowName),
    name,
    description,
    enabled: autoEnable,
    source: 'ci',
    metadata: {
      workflowName,
      ciType,
    },
    instructions,
  };
}

/**
 * Generate skills from a ProjectIndex
 *
 * @param projectIndex - The parsed project_index.json data
 * @param options - Generation options (which skill types to include, auto-enable)
 * @returns Result object with generated skills and any errors
 */
export function generateSkillsFromProjectIndex(
  projectIndex: ProjectIndex,
  options: SkillGenerationOptions = {},
): SkillGenerationResult {
  const {
    includeServices = true,
    includeDatabases = true,
    includeApis = true,
    includeCiWorkflows = true,
    autoEnable = false,
  } = options;

  const skills: Skill[] = [];
  const errors: Array<{ source: string; error: string }> = [];
  const existingNames = new Set<string>();

  // Generate service skills
  if (includeServices && projectIndex.services) {
    for (const [serviceName, serviceInfo] of Object.entries(projectIndex.services)) {
      try {
        const skill = generateServiceSkill(serviceName, serviceInfo, existingNames, autoEnable);
        skills.push(skill);
      } catch (error) {
        errors.push({
          source: `service:${serviceName}`,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    }
  }

  // Generate database model skills
  if (includeDatabases && projectIndex.services) {
    for (const [serviceName, serviceInfo] of Object.entries(projectIndex.services)) {
      if (serviceInfo.database?.models) {
        for (const [modelName, modelInfo] of Object.entries(serviceInfo.database.models)) {
          try {
            const skill = generateDatabaseSkill(
              serviceName,
              modelName,
              modelInfo as { orm?: string; fields: Record<string, unknown>; table?: string },
              existingNames,
              autoEnable,
            );
            skills.push(skill);
          } catch (error) {
            errors.push({
              source: `database:${serviceName}.${modelName}`,
              error: error instanceof Error ? error.message : 'Unknown error',
            });
          }
        }
      }
    }
  }

  // Generate API route skills
  if (includeApis && projectIndex.services) {
    for (const [serviceName, serviceInfo] of Object.entries(projectIndex.services)) {
      if (serviceInfo.api?.routes) {
        for (const route of serviceInfo.api.routes) {
          try {
            const skill = generateApiSkill(serviceName, route, existingNames, autoEnable);
            skills.push(skill);
          } catch (error) {
            errors.push({
              source: `api:${serviceName}.${route.path}`,
              error: error instanceof Error ? error.message : 'Unknown error',
            });
          }
        }
      }
    }
  }

  // Generate CI/CD workflow skills
  if (includeCiWorkflows && projectIndex.infrastructure?.ci_workflows) {
    const ciType = projectIndex.infrastructure.ci || 'CI/CD';
    for (const workflowName of projectIndex.infrastructure.ci_workflows) {
      try {
        const skill = generateCiWorkflowSkill(workflowName, ciType, existingNames, autoEnable);
        skills.push(skill);
      } catch (error) {
        errors.push({
          source: `ci:${workflowName}`,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    }
  }

  return {
    success: errors.length === 0,
    skills,
    errors: errors.length > 0 ? errors : undefined,
  };
}

/**
 * Parse project_index.json content and generate skills
 *
 * @param jsonContent - Raw JSON string from project_index.json
 * @param options - Generation options
 * @returns Result object with generated skills and any errors
 */
export function parseProjectIndexAndGenerateSkills(
  jsonContent: string,
  options: SkillGenerationOptions = {},
): SkillGenerationResult {
  try {
    const projectIndex: ProjectIndex = JSON.parse(jsonContent);
    return generateSkillsFromProjectIndex(projectIndex, options);
  } catch (error) {
    return {
      success: false,
      skills: [],
      errors: [
        {
          source: 'project_index',
          error: error instanceof Error ? error.message : 'Failed to parse project index JSON',
        },
      ],
    };
  }
}
