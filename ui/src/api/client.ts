import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response types
export interface ProjectSummary {
  project_id: string;
  name: string | null;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  latest_version_id: string | null;
  latest_status: string | null;
  latest_quality_score: number | null;
}

export interface VersionSummary {
  version_id: string;
  created_at: string;
  updated_at?: string | null;
  status: string;
  quality_score: number | null;
  summary: string;
  metrics: Record<string, any>;
  parent_version_id: string | null;
  progress: number;
}

export interface VersionDetail {
  version: VersionSummary;
  model_ir: Record<string, any>;
  analysis: Record<string, any>;
  code: Record<string, any>;
  tests: Record<string, any>;
  critique: Record<string, any> | null;
  plantuml_path: string | null;
  model_text: string | null;
  model_format: string | null;
}

export interface DiffResponse {
  from_version: string;
  to_version: string;
  summary: string;
  structure: Record<string, any>;
  relationships: Record<string, any>;
  metrics: Record<string, any>;
  findings: Record<string, any>;
}

export interface RecommendationSummary {
  rec_id: string;
  project_id: string;
  version_id: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  affected_entities: string[];
  design_pattern: string | null;
  rationale: string | null;
  created_at: string;
}

export interface CreateProjectRequest {
  project_id: string;
  name?: string;
  description?: string;
  tags?: string[];
}

export interface CreateVersionRequest {
  model_text: string;
  model_format: 'plantuml' | 'mermaid' | 'text';
  description?: string;
}

export interface UpdateVersionRequest {
  model_text: string;
  model_format: 'plantuml' | 'mermaid' | 'text';
}

export interface WorkflowJobResponse {
  job_id: string;
  project_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  message: string;
  version_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UpdateRecommendationRequest {
  status: 'open' | 'in_progress' | 'resolved' | 'dismissed';
  note?: string;
}

// API functions


export const versionsApi = {
  list: (projectId: string) => apiClient.get<VersionSummary[]>(`/projects/${projectId}/versions`),
  get: (projectId: string, versionId: string) => apiClient.get<VersionDetail>(`/projects/${projectId}/versions/${versionId}`),
  create: (projectId: string, data: CreateVersionRequest) => apiClient.post<VersionSummary>(`/projects/${projectId}/versions`, data),
  update: (projectId: string, versionId: string, data: UpdateVersionRequest) => apiClient.patch<VersionSummary>(`/projects/${projectId}/versions/${versionId}`, data),
  start: (projectId: string, versionId: string) => apiClient.post<WorkflowJobResponse>(`/projects/${projectId}/versions/${versionId}/start`),
  getPlantUML: (projectId: string, versionId: string) => apiClient.get<string>(`/projects/${projectId}/versions/${versionId}/plantuml`),
};

export const jobsApi = {
  get: (projectId: string, jobId: string) => apiClient.get<WorkflowJobResponse>(`/projects/${projectId}/jobs/${jobId}`),
  list: (projectId: string) => apiClient.get<WorkflowJobResponse[]>(`/projects/${projectId}/jobs`),
};

export const diffsApi = {
  compare: (projectId: string, fromVersion: string, toVersion: string) =>
    apiClient.get<DiffResponse>(`/projects/${projectId}/compare`, {
      params: { from: fromVersion, to: toVersion },
    }),
};

export const projectsApi = {
  list: () => apiClient.get<ProjectSummary[]>('/projects'),
  get: (projectId: string) => apiClient.get<ProjectSummary>(`/projects/${projectId}`),
  create: (data: CreateProjectRequest) => apiClient.post<ProjectSummary>('/projects', data),
  delete: (projectId: string) => apiClient.delete<ProjectSummary>(`/projects/${projectId}`),
};

export const recommendationsApi = {
  list: (projectId: string) =>
    apiClient.get<RecommendationSummary[]>(`/projects/${projectId}/recommendations`),
  listByVersion: (projectId: string, versionId: string) =>
    apiClient.get<RecommendationSummary[]>(`/projects/${projectId}/versions/${versionId}/recommendations`),
  update: (projectId: string, recId: string, data: UpdateRecommendationRequest) =>
    apiClient.post(`/projects/${projectId}/recommendations/${recId}`, data),
};
