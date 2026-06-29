import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusBadge } from "../components/StatusBadge";
import {
  FILE_BASED_CONNECTOR_TYPES,
  type ConnectorType,
  type NotificationChannelType,
  type TransformationType,
} from "../api/types";

const NOTIFICATION_CHANNEL_TYPES: NotificationChannelType[] = ["webhook", "email", "slack", "teams"];

const TRANSFORMATION_TYPES: TransformationType[] = [
  "standardize",
  "dedupe",
  "select_columns",
  "rename_columns",
  "fill_nulls",
  "filter_rows",
];

const CONNECTOR_TYPES: ConnectorType[] = [
  "csv",
  "json",
  "sqlite",
  "oracle",
  "postgres",
  "mysql",
  "mongodb",
  "s3",
  "rest_api",
  "servicenow",
  "jira",
  "confluence",
  "google_sheets",
];

const CONFIG_PLACEHOLDER: Record<string, string> = {
  sqlite: '{"db_path": "C:/data/app.db", "table": "customers"}',
  oracle: '{"host": "db.internal", "port": 1521, "service_name": "ORCL", "table": "customers"}',
  postgres: '{"host": "db.internal", "port": 5432, "database": "app", "table": "customers"}',
  mysql: '{"host": "db.internal", "port": 3306, "database": "app", "table": "customers"}',
  mongodb: '{"host": "db.internal", "port": 27017, "database": "app", "collection": "customers"}',
  s3: '{"bucket": "my-bucket", "key": "data/file.csv", "region": "us-east-1"}',
  rest_api: '{"base_url": "https://api.example.com", "path": "v1/things", "auth_type": "bearer"}',
  servicenow: '{"instance_url": "https://x.service-now.com", "table": "incident"}',
  jira: '{"base_url": "https://x.atlassian.net", "jql": "project = OPS"}',
  confluence: '{"base_url": "https://x.atlassian.net", "space_key": "ENG"}',
  google_sheets: '{"spreadsheet_id": "...", "range": "Sheet1!A1:B10"}',
};

const CREDENTIALS_PLACEHOLDER: Record<string, string> = {
  oracle: '{"username": "...", "password": "..."}',
  postgres: '{"username": "...", "password": "..."}',
  mysql: '{"username": "...", "password": "..."}',
  mongodb: '{"username": "...", "password": "..."} (optional -- omit for unauthenticated deployments)',
  s3: '{"access_key_id": "...", "secret_access_key": "..."} (optional -- omit to use the default AWS credential chain)',
  rest_api: '{"token": "..."} or {"username": "...", "password": "..."} or {"api_key": "..."}, matching auth_type',
  servicenow: '{"username": "...", "password": "..."}',
  jira: '{"email": "...", "api_token": "..."}',
  confluence: '{"email": "...", "api_token": "..."}',
  google_sheets: '{"api_key": "..."} or {"token": "..."}, matching auth_type',
};

function SourcesTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: sources } = useQuery({
    queryKey: ["sources", projectId],
    queryFn: () => api.listSources(projectId),
  });

  const [name, setName] = useState("");
  const [connectorType, setConnectorType] = useState<ConnectorType>("csv");
  const [connectionConfigText, setConnectionConfigText] = useState("");
  const [credentialsText, setCredentialsText] = useState("");
  const isFileBased = FILE_BASED_CONNECTOR_TYPES.includes(connectorType);

  const createSource = useMutation({
    mutationFn: () =>
      api.createSource(
        projectId,
        name,
        connectorType,
        connectionConfigText ? JSON.parse(connectionConfigText) : undefined,
        credentialsText ? JSON.parse(credentialsText) : undefined,
      ),
    onSuccess: () => {
      setName("");
      setConnectionConfigText("");
      setCredentialsText("");
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
        className="pipeline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createSource.mutate();
        }}
      >
        <div className="inline-form">
          <input
            placeholder="Source name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <select value={connectorType} onChange={(e) => setConnectorType(e.target.value as ConnectorType)}>
            {CONNECTOR_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        {!isFileBased && (
          <>
            <textarea
              rows={2}
              placeholder={`connection_config JSON, e.g. ${CONFIG_PLACEHOLDER[connectorType] ?? "{}"}`}
              value={connectionConfigText}
              onChange={(e) => setConnectionConfigText(e.target.value)}
            />
            <textarea
              rows={2}
              placeholder={`credentials JSON (encrypted at rest), e.g. ${CREDENTIALS_PLACEHOLDER[connectorType] ?? "{}"}`}
              value={credentialsText}
              onChange={(e) => setCredentialsText(e.target.value)}
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
            <th>Credentials</th>
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
              <td>{source.has_credentials ? "stored (encrypted)" : "—"}</td>
              <td>
                {FILE_BASED_CONNECTOR_TYPES.includes(source.connector_type) && (
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

function NotebooksTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: notebooks } = useQuery({
    queryKey: ["notebooks", projectId],
    queryFn: () => api.listNotebooks(projectId),
  });
  const { data: sources } = useQuery({
    queryKey: ["sources", projectId],
    queryFn: () => api.listSources(projectId),
  });

  const [name, setName] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sampleSize, setSampleSize] = useState(100);
  const createNotebook = useMutation({
    mutationFn: () => api.createNotebook(projectId, name, sourceId, sampleSize),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["notebooks", projectId] });
    },
  });

  return (
    <div>
      <p className="muted">
        Write pandas code in cells, run it against a small sample of a source's data to iterate
        quickly, then promote it into a real scheduled pipeline once it works.
      </p>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createNotebook.mutate();
        }}
      >
        <input
          placeholder="Notebook name"
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
          type="number"
          min={1}
          max={10000}
          value={sampleSize}
          onChange={(e) => setSampleSize(Number(e.target.value))}
          style={{ width: 90 }}
          title="Sample size (rows)"
        />
        <button type="submit" disabled={createNotebook.isPending}>
          Create notebook
        </button>
      </form>
      <ErrorBanner error={createNotebook.error} />

      <ul className="card-list">
        {notebooks?.map((notebook) => (
          <li key={notebook.id} className="card">
            <Link to={`/notebooks/${notebook.id}`}>
              <strong>{notebook.name}</strong>
              <span className="muted"> — {notebook.cells.length} cell(s)</span>
            </Link>{" "}
            <StatusBadge value={notebook.status} />
          </li>
        ))}
        {notebooks?.length === 0 && <p className="muted">No notebooks yet.</p>}
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

function NotificationChannelsTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: channels } = useQuery({
    queryKey: ["notification-channels", projectId],
    queryFn: () => api.listNotificationChannels(projectId),
  });

  const [channelType, setChannelType] = useState<NotificationChannelType>("webhook");
  const [url, setUrl] = useState("");
  const [toAddress, setToAddress] = useState("");
  const createChannel = useMutation({
    mutationFn: () =>
      api.createNotificationChannel(
        projectId,
        channelType,
        channelType === "email" ? { to_address: toAddress } : { url },
      ),
    onSuccess: () => {
      setUrl("");
      setToAddress("");
      queryClient.invalidateQueries({ queryKey: ["notification-channels", projectId] });
    },
  });

  const deleteChannel = useMutation({
    mutationFn: (channelId: string) => api.deleteNotificationChannel(channelId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notification-channels", projectId] }),
  });

  return (
    <div>
      <p className="muted">
        Fire a webhook, email, Slack, or Teams message whenever an Alert is created on this project.
      </p>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          createChannel.mutate();
        }}
      >
        <select
          value={channelType}
          onChange={(e) => setChannelType(e.target.value as NotificationChannelType)}
        >
          {NOTIFICATION_CHANNEL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {channelType === "email" ? (
          <input
            type="email"
            placeholder="oncall@example.com"
            value={toAddress}
            onChange={(e) => setToAddress(e.target.value)}
            required
          />
        ) : (
          <input
            placeholder={
              channelType === "slack"
                ? "https://hooks.slack.com/services/..."
                : channelType === "teams"
                  ? "https://outlook.office.com/webhook/..."
                  : "https://example.com/webhook"
            }
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
        )}
        <button type="submit" disabled={createChannel.isPending}>
          Add channel
        </button>
      </form>
      <ErrorBanner error={createChannel.error} />

      <table className="data-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Destination</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {channels?.map((channel) => (
            <tr key={channel.id}>
              <td>{channel.type}</td>
              <td>{(channel.config.url ?? channel.config.to_address ?? "—") as string}</td>
              <td>
                <button onClick={() => deleteChannel.mutate(channel.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {channels?.length === 0 && <p className="muted">No notification channels yet.</p>}
    </div>
  );
}

export function ProjectDetailPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const [tab, setTab] = useState<"sources" | "pipelines" | "notebooks" | "alerts" | "notifications">(
    "sources",
  );
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
        <button className={tab === "notebooks" ? "tab active" : "tab"} onClick={() => setTab("notebooks")}>
          Notebooks
        </button>
        <button className={tab === "alerts" ? "tab active" : "tab"} onClick={() => setTab("alerts")}>
          Alerts
        </button>
        <button
          className={tab === "notifications" ? "tab active" : "tab"}
          onClick={() => setTab("notifications")}
        >
          Notifications
        </button>
        <Link to={`/catalog?project_id=${projectId}`} className="tab">
          Catalog
        </Link>
      </div>

      {tab === "sources" && <SourcesTab projectId={projectId} />}
      {tab === "pipelines" && <PipelinesTab projectId={projectId} />}
      {tab === "notebooks" && <NotebooksTab projectId={projectId} />}
      {tab === "alerts" && <AlertsTab projectId={projectId} />}
      {tab === "notifications" && <NotificationChannelsTab projectId={projectId} />}
    </div>
  );
}
