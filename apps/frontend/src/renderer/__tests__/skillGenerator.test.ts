/**
 * Unit tests for Skill Generator
 * Tests skill generation from project_index.json
 */
import { describe, it, expect } from 'vitest';
import {
  generateSkillsFromProjectIndex,
  parseProjectIndexAndGenerateSkills,
} from '../utils/skillGenerator';
import type { ProjectIndex } from '../../shared/types/project';

describe('Skill Generator', () => {
  describe('generateSkillsFromProjectIndex', () => {
    it('should generate service skills from project index', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'monorepo',
        services: {
          frontend: {
            name: 'frontend',
            path: '/test/project/apps/frontend',
            language: 'TypeScript',
            framework: 'React',
            type: 'frontend',
            package_manager: 'npm',
            default_port: 3000,
          },
          backend: {
            name: 'backend',
            path: '/test/project/apps/backend',
            language: 'Python',
            type: 'backend',
            package_manager: 'pip',
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: true,
        includeDatabases: false,
        includeApis: false,
        includeCiWorkflows: false,
        autoEnable: false,
      });

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(2);

      const frontendSkill = result.skills.find((s) => s.metadata.serviceName === 'frontend');
      expect(frontendSkill).toBeDefined();
      expect(frontendSkill?.name).toBe('service-frontend');
      expect(frontendSkill?.description).toContain('frontend');
      expect(frontendSkill?.description).toContain('TypeScript');
      expect(frontendSkill?.description).toContain('React');
      expect(frontendSkill?.source).toBe('service');
      expect(frontendSkill?.enabled).toBe(false);
      expect(frontendSkill?.instructions).toContain('frontend service');

      const backendSkill = result.skills.find((s) => s.metadata.serviceName === 'backend');
      expect(backendSkill).toBeDefined();
      expect(backendSkill?.name).toBe('service-backend');
      expect(backendSkill?.description).toContain('backend');
      expect(backendSkill?.description).toContain('Python');
    });

    it('should generate database model skills from project index', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
            database: {
              total_models: 2,
              model_names: ['User', 'Post'],
              models: {
                User: {
                  orm: 'SQLAlchemy',
                  fields: {
                    id: { type: 'Integer', primary_key: true },
                    email: { type: 'String', primary_key: false },
                    name: { type: 'String', primary_key: false },
                  },
                  table: 'users',
                },
                Post: {
                  orm: 'SQLAlchemy',
                  fields: {
                    id: { type: 'Integer', primary_key: true },
                    title: { type: 'String', primary_key: false },
                    content: { type: 'Text', primary_key: false },
                    user_id: { type: 'Integer', primary_key: false },
                  },
                  table: 'posts',
                },
              },
            },
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: false,
        includeDatabases: true,
        includeApis: false,
        includeCiWorkflows: false,
        autoEnable: true,
      });

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(2);

      const userSkill = result.skills.find((s) => s.metadata.modelName === 'User');
      expect(userSkill).toBeDefined();
      expect(userSkill?.name).toBe('db-model-user');
      expect(userSkill?.description).toContain('User');
      expect(userSkill?.description).toContain('SQLAlchemy');
      expect(userSkill?.source).toBe('database');
      expect(userSkill?.enabled).toBe(true);
      expect(userSkill?.instructions).toContain('User database model');
      expect(userSkill?.instructions).toContain('users');
      expect(userSkill?.instructions).toContain('id');
      expect(userSkill?.instructions).toContain('email');

      const postSkill = result.skills.find((s) => s.metadata.modelName === 'Post');
      expect(postSkill).toBeDefined();
      expect(postSkill?.name).toBe('db-model-post');
    });

    it('should generate API route skills from project index', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
            api: {
              total_routes: 2,
              routes: [
                {
                  path: '/api/users',
                  methods: ['GET', 'POST'],
                  framework: 'FastAPI',
                  requires_auth: false,
                },
                {
                  path: '/api/posts',
                  methods: ['GET'],
                  framework: 'FastAPI',
                  requires_auth: true,
                },
              ],
            },
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: false,
        includeDatabases: false,
        includeApis: true,
        includeCiWorkflows: false,
      });

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(2);

      const usersSkill = result.skills.find((s) => s.metadata.path === '/api/users');
      expect(usersSkill).toBeDefined();
      expect(usersSkill?.name).toBe('api-get-post-api-users');
      expect(usersSkill?.description).toContain('GET/POST');
      expect(usersSkill?.description).toContain('/api/users');
      expect(usersSkill?.description).toContain('FastAPI');
      expect(usersSkill?.source).toBe('api');
      expect(usersSkill?.instructions).toContain('/api/users');

      const postsSkill = result.skills.find((s) => s.metadata.path === '/api/posts');
      expect(postsSkill).toBeDefined();
      expect(postsSkill?.name).toBe('api-get-api-posts');
      expect(postsSkill?.instructions).toContain('requires authentication');
    });

    it('should generate CI/CD workflow skills from project index', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {},
        infrastructure: {
          ci: 'GitHub Actions',
          ci_workflows: ['ci.yml', 'release.yml', 'test.yml'],
        },
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: false,
        includeDatabases: false,
        includeApis: false,
        includeCiWorkflows: true,
      });

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(3);

      const ciSkill = result.skills.find((s) => s.metadata.workflowName === 'ci.yml');
      expect(ciSkill).toBeDefined();
      expect(ciSkill?.name).toBe('ci-ci');
      expect(ciSkill?.description).toContain('ci.yml');
      expect(ciSkill?.description).toContain('CI/CD workflow');
      expect(ciSkill?.source).toBe('ci');
      expect(ciSkill?.instructions).toContain('GitHub Actions');

      const releaseSkill = result.skills.find((s) => s.metadata.workflowName === 'release.yml');
      expect(releaseSkill).toBeDefined();
      expect(releaseSkill?.name).toBe('ci-release');
    });

    it('should generate all skill types when all options are enabled', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
            database: {
              total_models: 1,
              model_names: ['User'],
              models: {
                User: {
                  orm: 'SQLAlchemy',
                  fields: { id: { type: 'Integer', primary_key: true } },
                },
              },
            },
            api: {
              total_routes: 1,
              routes: [
                {
                  path: '/api/users',
                  methods: ['GET'],
                  framework: 'FastAPI',
                },
              ],
            },
          },
        },
        infrastructure: {
          ci: 'GitHub Actions',
          ci_workflows: ['ci.yml'],
        },
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: true,
        includeDatabases: true,
        includeApis: true,
        includeCiWorkflows: true,
      });

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(4);

      const sources = result.skills.map((s) => s.source);
      expect(sources).toContain('service');
      expect(sources).toContain('database');
      expect(sources).toContain('api');
      expect(sources).toContain('ci');
    });

    it('should handle duplicate skill names by appending numeric suffix', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'monorepo',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project/apps/backend',
            language: 'Python',
            type: 'backend',
          },
          'backend-v2': {
            name: 'backend-v2',
            path: '/test/project/apps/backend-v2',
            language: 'Python',
            type: 'backend',
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(2);

      const names = result.skills.map((s) => s.name);
      expect(names).toContain('service-backend');
      expect(names).toContain('service-backend-v2');
    });

    it('should sanitize skill names to lowercase with hyphens only', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          'My Service!': {
            name: 'My Service!',
            path: '/test/project',
            language: 'TypeScript',
            type: 'frontend',
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(1);
      expect(result.skills[0].name).toBe('service-my-service');
      expect(result.skills[0].name).toMatch(/^[a-z0-9-]+$/);
    });

    it('should return empty array when no services or infrastructure', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {},
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(0);
    });

    it('should handle missing optional fields gracefully', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          minimal: {
            name: 'minimal',
            path: '/test/project',
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(1);
      expect(result.skills[0].name).toBe('service-minimal');
      expect(result.skills[0].description).toContain('minimal');
    });
  });

  describe('parseProjectIndexAndGenerateSkills', () => {
    it('should parse valid JSON and generate skills', () => {
      const jsonContent = JSON.stringify({
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
          },
        },
        infrastructure: {},
        conventions: {},
      });

      const result = parseProjectIndexAndGenerateSkills(jsonContent);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(1);
      expect(result.skills[0].name).toBe('service-backend');
    });

    it('should handle invalid JSON gracefully', () => {
      const invalidJson = '{ invalid json content }';

      const result = parseProjectIndexAndGenerateSkills(invalidJson);

      expect(result.success).toBe(false);
      expect(result.skills).toHaveLength(0);
      expect(result.errors).toBeDefined();
      expect(result.errors?.[0].source).toBe('project_index');
      expect(result.errors?.[0].error).toContain('JSON');
    });

    it('should handle empty JSON object', () => {
      const jsonContent = JSON.stringify({
        project_root: '/test/project',
        project_type: 'single',
        services: {},
        infrastructure: {},
        conventions: {},
      });

      const result = parseProjectIndexAndGenerateSkills(jsonContent);

      expect(result.success).toBe(true);
      expect(result.skills).toHaveLength(0);
    });
  });

  describe('Skill content generation', () => {
    it('should generate proper instructions for service skills', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project/backend',
            language: 'Python',
            framework: 'FastAPI',
            type: 'backend',
            package_manager: 'pip',
            default_port: 8000,
            entry_point: 'main.py',
            key_directories: {
              api: { path: 'api', purpose: 'API routes' },
              models: { path: 'models', purpose: 'Database models' },
            },
            dependencies: ['fastapi', 'uvicorn', 'sqlalchemy'],
            testing: 'pytest',
            test_directory: 'tests',
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex);

      expect(result.success).toBe(true);
      const skill = result.skills[0];

      expect(skill.instructions).toContain('## Purpose');
      expect(skill.instructions).toContain('## Usage');
      expect(skill.instructions).toContain('## Service Location');
      expect(skill.instructions).toContain('## Key Directories');
      expect(skill.instructions).toContain('## Dependencies');
      expect(skill.instructions).toContain('## Testing');
      expect(skill.instructions).toContain('## Examples');

      expect(skill.instructions).toContain('Python');
      expect(skill.instructions).toContain('FastAPI');
      expect(skill.instructions).toContain('8000');
      expect(skill.instructions).toContain('main.py');
      expect(skill.instructions).toContain('api');
      expect(skill.instructions).toContain('API routes');
      expect(skill.instructions).toContain('fastapi');
      expect(skill.instructions).toContain('pytest');
      expect(skill.instructions).toContain('tests');
    });

    it('should generate proper instructions for database skills', () => {
      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
            database: {
              total_models: 1,
              model_names: ['User'],
              models: {
                User: {
                  orm: 'SQLAlchemy',
                  table: 'users',
                  fields: {
                    id: { type: 'Integer', primary_key: true },
                    email: { type: 'String', primary_key: false },
                    password: { type: 'String', primary_key: false },
                    created_at: { type: 'DateTime', primary_key: false },
                  },
                },
              },
            },
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: false,
        includeDatabases: true,
      });

      expect(result.success).toBe(true);
      const skill = result.skills[0];

      expect(skill.instructions).toContain('## Purpose');
      expect(skill.instructions).toContain('## Schema');
      expect(skill.instructions).toContain('## Usage');
      expect(skill.instructions).toContain('## Examples');

      expect(skill.instructions).toContain('SQLAlchemy');
      expect(skill.instructions).toContain('users');
      expect(skill.instructions).toContain('id');
      expect(skill.instructions).toContain('Integer');
      expect(skill.instructions).toContain('Primary Key');
      expect(skill.instructions).toContain('email');
      expect(skill.instructions).toContain('password');
    });

    it('should truncate field list when more than 10 fields', () => {
      const fields: Record<string, unknown> = {};
      for (let i = 1; i <= 15; i++) {
        fields[`field${i}`] = { type: 'String', primary_key: false };
      }

      const projectIndex: ProjectIndex = {
        project_root: '/test/project',
        project_type: 'single',
        services: {
          backend: {
            name: 'backend',
            path: '/test/project',
            language: 'Python',
            type: 'backend',
            database: {
              total_models: 1,
              model_names: ['LargeModel'],
              models: {
                LargeModel: {
                  orm: 'SQLAlchemy',
                  fields,
                },
              },
            },
          },
        },
        infrastructure: {},
        conventions: {},
      };

      const result = generateSkillsFromProjectIndex(projectIndex, {
        includeServices: false,
        includeDatabases: true,
      });

      expect(result.success).toBe(true);
      const skill = result.skills[0];

      expect(skill.instructions).toContain('and 5 more fields');
    });
  });
});
