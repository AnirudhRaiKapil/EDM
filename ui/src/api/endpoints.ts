import { apiClient } from "./client";
import type {
  Alert,
  CellRunResult,
  Dataset,
  DatasetDetail,
  Job,
  LineageGraph,
  Member,
  Notebook,
  NotebookCell,
  Pipeline,
  Project,
  QualityRule,
  QualityRun,
  QueryResult,
  Source,
  Tag,
  Transformation,
  User,
  Workspace,
} from "./types";

export async function register(email: string, display_name: string, password: string) {
  const { data } = await apiClient.post<User>("/auth/register", { email, display_name, password });
  return data;
}

export async function login(email: string, password: string) {
  const { data } = await apiClient.post<{ access_token: string }>("/auth/login", { email, password });
  return data;
}

export async function whoami() {
  const { data } = await apiClient.get<User>("/users/me");
  return data;
}

export async function listWorkspaces() {
  const { data } = await apiClient.get<Workspace[]>("/workspaces");
  return data;
}

export async function createWorkspace(name: string, description: string) {
  const { data } = await apiClient.post<Workspace>("/workspaces", { name, description });
  return data;
}

export async function getWorkspace(workspaceId: string) {
  const { data } = await apiClient.get<Workspace>(`/workspaces/${workspaceId}`);
  return data;
}

export async function listMembers(workspaceId: string) {
  const { data } = await apiClient.get<Member[]>(`/workspaces/${workspaceId}/members`);
  return data;
}

export async function addMember(workspaceId: string, email: string, role: "owner" | "member") {
  const { data } = await apiClient.post<Member>(`/workspaces/${workspaceId}/members`, { email, role });
  return data;
}

export async function listProjects(workspaceId: string) {
  const { data } = await apiClient.get<Project[]>(`/workspaces/${workspaceId}/projects`);
  return data;
}

export async function createProject(workspaceId: string, name: string, environment: string) {
  const { data } = await apiClient.post<Project>(`/workspaces/${workspaceId}/projects`, {
    name,
    environment,
  });
  return data;
}

export async function listSources(projectId: string) {
  const { data } = await apiClient.get<Source[]>(`/projects/${projectId}/sources`);
  return data;
}

export async function createSource(
  projectId: string,
  name: string,
  connector_type: string,
  connection_config?: Record<string, unknown>,
  credentials?: Record<string, unknown>,
) {
  const { data } = await apiClient.post<Source>(`/projects/${projectId}/sources`, {
    name,
    connector_type,
    connection_config,
    credentials,
  });
  return data;
}

export async function uploadSourceFile(sourceId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<Source>(`/sources/${sourceId}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listPipelines(projectId: string) {
  const { data } = await apiClient.get<Pipeline[]>(`/projects/${projectId}/pipelines`);
  return data;
}

export async function createPipeline(
  projectId: string,
  name: string,
  sourceId: string,
  outputDatasetName: string,
  outputLayer: string,
  transformations: Pick<Transformation, "type" | "order" | "parameters">[],
) {
  const { data } = await apiClient.post<Pipeline>(`/projects/${projectId}/pipelines`, {
    name,
    source_id: sourceId,
    output_dataset_name: outputDatasetName,
    output_layer: outputLayer,
    transformations,
  });
  return data;
}

export async function getPipeline(pipelineId: string) {
  const { data } = await apiClient.get<Pipeline>(`/pipelines/${pipelineId}`);
  return data;
}

export async function runPipeline(pipelineId: string) {
  const { data } = await apiClient.post<Job>(`/pipelines/${pipelineId}/jobs`);
  return data;
}

export async function setPipelineSchedule(pipelineId: string, cron: string | null) {
  const { data } = await apiClient.patch<Pipeline>(`/pipelines/${pipelineId}/schedule`, { cron });
  return data;
}

export async function listJobs(pipelineId: string) {
  const { data } = await apiClient.get<Job[]>(`/pipelines/${pipelineId}/jobs`);
  return data;
}

export async function getJob(jobId: string) {
  const { data } = await apiClient.get<Job>(`/jobs/${jobId}`);
  return data;
}

export async function searchDatasets(params: {
  project_id?: string;
  q?: string;
  tag_key?: string;
  tag_value?: string;
}) {
  const { data } = await apiClient.get<Dataset[]>("/catalog/datasets", { params });
  return data;
}

export async function getDataset(datasetId: string) {
  const { data } = await apiClient.get<DatasetDetail>(`/catalog/datasets/${datasetId}`);
  return data;
}

export async function updateClassification(datasetId: string, classification: string[]) {
  const { data } = await apiClient.patch<Dataset>(`/catalog/datasets/${datasetId}`, { classification });
  return data;
}

export async function addTag(datasetId: string, key: string, value: string) {
  const { data } = await apiClient.post<Tag>(`/catalog/datasets/${datasetId}/tags`, { key, value });
  return data;
}

export async function removeTag(datasetId: string, tagId: string) {
  await apiClient.delete(`/catalog/datasets/${datasetId}/tags/${tagId}`);
}

export async function listQualityRules(datasetId: string) {
  const { data } = await apiClient.get<QualityRule[]>(`/catalog/datasets/${datasetId}/quality-rules`);
  return data;
}

export async function addQualityRule(
  datasetId: string,
  expectation_type: string,
  parameters: Record<string, unknown>,
  severity: string,
) {
  const { data } = await apiClient.post<QualityRule>(`/catalog/datasets/${datasetId}/quality-rules`, {
    expectation_type,
    parameters,
    severity,
  });
  return data;
}

export async function deleteQualityRule(datasetId: string, ruleId: string) {
  await apiClient.delete(`/catalog/datasets/${datasetId}/quality-rules/${ruleId}`);
}

export async function listQualityRuns(datasetId: string) {
  const { data } = await apiClient.get<QualityRun[]>(`/catalog/datasets/${datasetId}/quality-runs`);
  return data;
}

export async function getDatasetLineage(datasetId: string) {
  const { data } = await apiClient.get<LineageGraph>(`/lineage/datasets/${datasetId}`);
  return data;
}

export async function listAlerts(projectId: string, status?: string) {
  const { data } = await apiClient.get<Alert[]>(`/projects/${projectId}/alerts`, {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function updateAlertStatus(alertId: string, status: string) {
  const { data } = await apiClient.patch<Alert>(`/alerts/${alertId}`, { status });
  return data;
}

export async function runQuery(datasetId: string, sql: string) {
  const { data } = await apiClient.post<QueryResult>("/query", { dataset_id: datasetId, sql });
  return data;
}

export async function listNotebooks(projectId: string) {
  const { data } = await apiClient.get<Notebook[]>(`/projects/${projectId}/notebooks`);
  return data;
}

export async function createNotebook(
  projectId: string,
  name: string,
  sourceId: string,
  sampleSize: number,
) {
  const { data } = await apiClient.post<Notebook>(`/projects/${projectId}/notebooks`, {
    name,
    source_id: sourceId,
    sample_size: sampleSize,
  });
  return data;
}

export async function getNotebook(notebookId: string) {
  const { data } = await apiClient.get<Notebook>(`/notebooks/${notebookId}`);
  return data;
}

export async function addNotebookCell(notebookId: string, code: string) {
  const { data } = await apiClient.post<NotebookCell>(`/notebooks/${notebookId}/cells`, { code });
  return data;
}

export async function updateNotebookCell(notebookId: string, cellId: string, code: string) {
  const { data } = await apiClient.patch<NotebookCell>(
    `/notebooks/${notebookId}/cells/${cellId}`,
    { code },
  );
  return data;
}

export async function deleteNotebookCell(notebookId: string, cellId: string) {
  await apiClient.delete(`/notebooks/${notebookId}/cells/${cellId}`);
}

export async function runNotebook(notebookId: string, upToCellId?: string) {
  const { data } = await apiClient.post<{ results: CellRunResult[] }>(
    `/notebooks/${notebookId}/run`,
    undefined,
    { params: upToCellId ? { up_to_cell_id: upToCellId } : undefined },
  );
  return data.results;
}

export async function promoteNotebook(
  notebookId: string,
  outputDatasetName: string,
  outputLayer: string,
  pipelineName?: string,
) {
  const { data } = await apiClient.post<Pipeline>(`/notebooks/${notebookId}/promote`, {
    output_dataset_name: outputDatasetName,
    output_layer: outputLayer,
    pipeline_name: pipelineName,
  });
  return data;
}
