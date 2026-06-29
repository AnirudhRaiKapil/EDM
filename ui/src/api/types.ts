export interface User {
  id: string;
  email: string;
  display_name: string;
  status: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  status: string;
  owner_id: string;
  created_at: string;
}

export interface Member {
  user_id: string;
  email: string;
  role_name: "owner" | "member";
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  environment: string;
  status: string;
  owner_id: string;
  created_at: string;
}

export type ConnectorType =
  | "csv"
  | "json"
  | "sqlite"
  | "oracle"
  | "s3"
  | "rest_api"
  | "servicenow"
  | "jira"
  | "confluence"
  | "postgres"
  | "mysql"
  | "mongodb"
  | "google_sheets";

export const FILE_BASED_CONNECTOR_TYPES: ConnectorType[] = ["csv", "json"];

export interface Source {
  id: string;
  project_id: string;
  name: string;
  connector_type: ConnectorType;
  ingestion_mode: string;
  status: string;
  raw_file_path: string | null;
  connection_config: Record<string, unknown> | null;
  has_credentials: boolean;
  owner_id: string;
  created_at: string;
}

export type TransformationType =
  | "standardize"
  | "dedupe"
  | "select_columns"
  | "rename_columns"
  | "fill_nulls"
  | "filter_rows"
  | "python_code";

export interface Transformation {
  id: string;
  type: TransformationType;
  order: number;
  parameters: Record<string, unknown>;
}

export interface Pipeline {
  id: string;
  project_id: string;
  source_id: string;
  name: string;
  version: number;
  output_dataset_name: string;
  output_layer: "bronze" | "silver" | "gold";
  status: string;
  schedule_cron: string | null;
  owner_id: string;
  created_at: string;
  transformations: Transformation[];
}

export interface NotebookCell {
  id: string;
  notebook_id: string;
  order: number;
  code: string;
}

export interface Notebook {
  id: string;
  project_id: string;
  source_id: string;
  name: string;
  sample_size: number;
  status: "draft" | "promoted";
  promoted_pipeline_id: string | null;
  owner_id: string;
  created_at: string;
  cells: NotebookCell[];
}

export interface CellRunResult {
  cell_id: string;
  status: "ok" | "error" | "skipped";
  stdout: string;
  preview: Record<string, unknown>[];
  row_count: number | null;
  columns: string[] | null;
  error: string | null;
}

export interface Job {
  id: string;
  pipeline_id: string;
  pipeline_version: number;
  status: "queued" | "running" | "succeeded" | "failed";
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  metrics: { rowsIn?: number; rowsOut?: number; qualityOutcome?: string | null };
  error_message: string | null;
  dataset_id: string | null;
  created_at: string;
}

export interface ColumnInfo {
  name: string;
  data_type: string;
  nullable: boolean;
  description: string;
}

export interface SchemaInfo {
  id: string;
  dataset_id: string;
  version: number;
  status: string;
  columns: ColumnInfo[];
}

export interface Tag {
  id: string;
  key: string;
  value: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  layer: "bronze" | "silver" | "gold";
  physical_location: string;
  classification: string[];
  status: string;
  quality_score: number | null;
  owner_id: string;
  created_at: string;
}

export interface DatasetDetail extends Dataset {
  schema_info: SchemaInfo | null;
  tags: Tag[];
}

export type ExpectationType = "not_null" | "unique" | "min" | "max" | "regex" | "allowed_values";

export interface QualityRule {
  id: string;
  dataset_id: string;
  expectation_type: ExpectationType;
  parameters: Record<string, unknown>;
  severity: "warning" | "blocking";
  created_at: string;
}

export interface QualityRunResult {
  ruleId: string;
  expectationType: string;
  severity: string;
  passed: boolean;
  details: Record<string, unknown>;
}

export interface QualityRun {
  id: string;
  dataset_id: string;
  job_id: string | null;
  results: QualityRunResult[];
  outcome: "passed" | "passed_with_warnings" | "failed";
  created_at: string;
}

export interface LineageEdge {
  id: string;
  from_entity_type: string;
  from_entity_id: string;
  to_entity_type: string;
  to_entity_id: string;
  job_id: string | null;
  created_at: string;
}

export interface LineageGraph {
  entity_type: string;
  entity_id: string;
  upstream: LineageEdge[];
  downstream: LineageEdge[];
}

export interface Alert {
  id: string;
  project_id: string;
  source_entity_type: string;
  source_entity_id: string;
  severity: "info" | "warning" | "critical";
  message: string;
  status: "open" | "acknowledged" | "resolved";
  created_at: string;
}

export interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  subject_email: string | null;
  workspace_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export type NotificationChannelType = "webhook" | "email" | "slack" | "teams";

export interface NotificationChannel {
  id: string;
  project_id: string;
  type: NotificationChannelType;
  config: Record<string, unknown>;
  enabled: boolean;
  owner_id: string;
  created_at: string;
}
