import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusBadge } from "../components/StatusBadge";
import type { ConnectorType, TransformationType } from "../api/types";

const TRANSFORMATION_TYPES: TransformationType[] = [
  "standardize",
  "dedupe",
  "select_columns",
  "rename_columns",
  "fill_nulls",
  "filter_rows",
];

function SourcesTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: sources } = useQuery({
    queryKey: ["sources", projectId],
    queryFn: () => api.listSources(projectId),
  });

  const [name, setName] = useState("");
  const [connectorType, setConnectorType] = useState<ConnectorType>("csv");
  const [dbPath, setDbPath] = useState("");
  const [table, setTable] = useState("");
  const createSource = useMutation({
    mutationFn: () =>
      api.createSource(
        projectId,
        name,
        connectorType,
        connectorType === "sqlite" ? { db_path: dbPath, table } : undefined,
      ),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["sources", projectId] });
    },
  });

  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const uploadFile = useMutation({
    mutationFn: ({ sourceId, file }: { sourceId: string; file: File }) =>
      api.uploadSourceFile(sourceId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources", projectId] }),
    onSettled: () => setUploadingId(null),
  });

  return (
    <div>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createSource.mutate();
        }}
      >
        <input placeholder="Source name" value={name} onChange={(e) => setName(e.target.value)} required />
        <select value={connectorType} onChange={(e) => setConnectorType(e.target.value as ConnectorType)}>
          <option value="csv">csv</option>
          <option value="json">json</option>
          <option value="sqlite">sqlite</option>
        </select>
        {connectorType === "sqlite" && (
          <>
            <input
              placeholder="db_path (e.g. C:/data/app.db)"
              value={dbPath}
              onChange={(e) => setDbPath(e.target.value)}
              required
            />
            <input
              placeholder="table name"
              value={table}
              onChange={(e) => setTable(e.target.value)}
              required
            />
          </>
        )}
        <button type="submit" disabled={createSource.isPending}>
          Create source
        </button>
      </form>
      <ErrorBanner error={createSource.error} />

      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>File / Config</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sources?.map((source) => (
            <tr key={source.id}>
              <td>{source.name}</td>
              <td>{source.connector_type}</td>
              <td>
                {source.raw_file_path ??
                  (source.connection_config ? JSON.stringify(source.connection_config) : "—")}
              </td>
              <td>
                {source.connector_type !== "sqlite" && (
                  <>
                    <input
                      type="file"
                      id={`upload-${source.id}`}
                      style={{ display: "none" }}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          setUploadingId(source.id);
                          uploadFile.mutate({ sourceId: source.id, file });
                        }
                      }}
                    />
                    <label htmlFor={`upload-${source.id}`} className="link-button">
                      {uploadingId === source.id ? "Uploading..." : "Upload file"}
                    </label>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ErrorBanner error={uploadFile.error} />
    </div>
  );
}

function PipelinesTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: pipelines } = useQuery({
    queryKey: ["pipelines", projectId],
    queryFn: () => api.listPipelines(projectId),
  });
  const { data: sources } = useQuery({
    queryKey: ["sources", projectId],
    queryFn: () => api.listSources(projectId),
  });

  const [name, setName] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [outputDatasetName, setOutputDatasetName] = useState("");
  const [outputLayer, setOutputLayer] = useState("silver");
  const [steps, setSteps] = useState<{ type: TransformationType; parameters: string }[]>([]);

  const createPipeline = useMutation({
    mutationFn: () =>
      api.createPipeline(
        projectId,
        name,
        sourceId,
        outputDatasetName,
        outputLayer,
        steps.map((s, i) => ({ type: s.type, order: i, parameters: JSON.parse(s.parameters || "{}") })),
      ),
    onSuccess: () => {
      setName("");
      setOutputDatasetName("");
      setSteps([]);
      queryClient.invalidateQueries({ queryKey: ["pipelines", projectId] });
    },
  });

  return (
    <div>
      <form
        className="pipeline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createPipeline.mutate();
        }}
      >
        <div className="inline-form">
          <input
            placeholder="Pipeline name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
            <option value="">Select source...</option>
            {sources?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Output dataset name"
            value={outputDatasetName}
            onChange={(e) => setOutputDatasetName(e.target.value)}
            required
          />
          <select value={outputLayer} onChange={(e) => setOutputLayer(e.target.value)}>
            <option value="bronze">bronze</option>
            <option value="silver">silver</option>
            <option value="gold">gold</option>
          </select>
        </div>

        <div className="steps-builder">
          <strong>Transformations</strong>
          {steps.map((step, i) => (
            <div className="inline-form" key={i}>
              <select
                value={step.type}
                onChange={(e) => {
                  const next = [...steps];
                  next[i] = { ...next[i], type: e.target.value as TransformationType };
                  setSteps(next);
                }}
              >
                {TRANSFORMATION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                placeholder='parameters JSON, e.g. {"column": "email"}'
                value={step.parameters}
                onChange={(e) => {
                  const next = [...steps];
                  next[i] = { ...next[i], parameters: e.target.value };
                  setSteps(next);
                }}
              />
              <button type="button" onClick={() => setSteps(steps.filter((_, j) => j !== i))}>
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setSteps([...steps, { type: "standardize", parameters: "{}" }])}
          >
            + Add transformation
          </button>
        </div>

        <button type="submit" disabled={createPipeline.isPending}>
          Create pipeline
        </button>
      </form>
      <ErrorBanner error={createPipeline.error} />

      <ul className="card-list">
        {pipelines?.map((pipeline) => (
          <li key={pipeline.id} className="card">
            <Link to={`/pipelines/${pipeline.id}`}>
              <strong>{pipeline.name}</strong>
              <span className="muted">
                {" "}
                — {pipeline.output_dataset_name} ({pipeline.output_layer})
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AlertsTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const { data: alerts } = useQuery({
    queryKey: ["alerts", projectId, statusFilter],
    queryFn: () => api.listAlerts(projectId, statusFilter || undefined),
  });

  const updateStatus = useMutation({
    mutationFn: ({ alertId, status }: { alertId: string; status: string }) =>
      api.updateAlertStatus(alertId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts", projectId] }),
  });

  return (
    <div>
      <div className="inline-form">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="open">open</option>
          <option value="acknowledged">acknowledged</option>
          <option value="resolved">resolved</option>
          <option value="">all</option>
        </select>
      </div>

      <ul className="card-list">
        {alerts?.map((alert) => (
          <li key={alert.id} className="card rule-card">
            <StatusBadge value={alert.severity} />
            <StatusBadge value={alert.status} />
            <span>{alert.message}</span>
            <span className="muted">{new Date(alert.created_at).toLocaleString()}</span>
            {alert.status !== "acknowledged" && (
              <button onClick={() => updateStatus.mutate({ alertId: alert.id, status: "acknowledged" })}>
                Acknowledge
              </button>
            )}
            {alert.status !== "resolved" && (
              <button onClick={() => updateStatus.mutate({ alertId: alert.id, status: "resolved" })}>
                Resolve
              </button>
            )}
          </li>
        ))}
        {alerts?.length === 0 && <p className="muted">No {statusFilter || ""} alerts.</p>}
      </ul>
    </div>
  );
}

export function ProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const [tab, setTab] = useState<"sources" | "pipelines" | "alerts">("sources");
  if (!workspaceId || !projectId) return null;

  return (
    <div className="page">
      <Link to={`/workspaces/${workspaceId}`} className="back-link">
        &larr; Workspace
      </Link>
      <h1>Project</h1>

      <div className="tabs">
        <button className={tab === "sources" ? "tab active" : "tab"} onClick={() => setTab("sources")}>
          Sources
        </button>
        <button className={tab === "pipelines" ? "tab active" : "tab"} onClick={() => setTab("pipelines")}>
          Pipelines
        </button>
        <button className={tab === "alerts" ? "tab active" : "tab"} onClick={() => setTab("alerts")}>
          Alerts
        </button>
        <Link to={`/catalog?project_id=${projectId}`} className="tab">
          Catalog
        </Link>
      </div>

      {tab === "sources" && <SourcesTab projectId={projectId} />}
      {tab === "pipelines" && <PipelinesTab projectId={projectId} />}
      {tab === "alerts" && <AlertsTab projectId={projectId} />}
    </div>
  );
}
