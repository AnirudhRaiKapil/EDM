import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusBadge } from "../components/StatusBadge";
import type { ExpectationType } from "../api/types";

const EXPECTATION_TYPES: ExpectationType[] = ["not_null", "unique", "min", "max", "regex", "allowed_values"];

function SchemaSection({ datasetId }: { datasetId: string }) {
  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId),
  });

  return (
    <section>
      <h2>Schema (version {dataset?.schema_info?.version ?? "—"})</h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>Column</th>
            <th>Type</th>
            <th>Nullable</th>
          </tr>
        </thead>
        <tbody>
          {dataset?.schema_info?.columns.map((c) => (
            <tr key={c.name}>
              <td>{c.name}</td>
              <td>{c.data_type}</td>
              <td>{c.nullable ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function TagsAndClassificationSection({ datasetId }: { datasetId: string }) {
  const queryClient = useQueryClient();
  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId),
  });

  const [tagKey, setTagKey] = useState("");
  const [tagValue, setTagValue] = useState("");
  const addTag = useMutation({
    mutationFn: () => api.addTag(datasetId, tagKey, tagValue),
    onSuccess: () => {
      setTagKey("");
      setTagValue("");
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
    },
  });
  const removeTag = useMutation({
    mutationFn: (tagId: string) => api.removeTag(datasetId, tagId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] }),
  });

  const [classification, setClassification] = useState("");
  const updateClassification = useMutation({
    mutationFn: () =>
      api.updateClassification(
        datasetId,
        classification.split(",").map((c) => c.trim()).filter(Boolean),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] }),
  });

  return (
    <section>
      <h2>Tags & classification</h2>
      <p>
        Classification: {dataset?.classification.join(", ") || "none"}
      </p>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          updateClassification.mutate();
        }}
      >
        <input
          placeholder="comma-separated, e.g. pii, confidential"
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
        />
        <button type="submit" disabled={updateClassification.isPending}>
          Update classification
        </button>
      </form>
      <ErrorBanner error={updateClassification.error} />

      <div className="tag-list">
        {dataset?.tags.map((tag) => (
          <span className="tag-chip" key={tag.id}>
            {tag.key}={tag.value}
            <button onClick={() => removeTag.mutate(tag.id)}>&times;</button>
          </span>
        ))}
      </div>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          addTag.mutate();
        }}
      >
        <input placeholder="key" value={tagKey} onChange={(e) => setTagKey(e.target.value)} required />
        <input placeholder="value" value={tagValue} onChange={(e) => setTagValue(e.target.value)} required />
        <button type="submit" disabled={addTag.isPending}>
          Add tag
        </button>
      </form>
      <ErrorBanner error={addTag.error} />
    </section>
  );
}

function QualitySection({ datasetId }: { datasetId: string }) {
  const queryClient = useQueryClient();
  const { data: rules } = useQuery({
    queryKey: ["quality-rules", datasetId],
    queryFn: () => api.listQualityRules(datasetId),
  });
  const { data: runs } = useQuery({
    queryKey: ["quality-runs", datasetId],
    queryFn: () => api.listQualityRuns(datasetId),
  });

  const [expectationType, setExpectationType] = useState<ExpectationType>("not_null");
  const [column, setColumn] = useState("");
  const [severity, setSeverity] = useState<"warning" | "blocking">("blocking");
  const [value, setValue] = useState("");

  const addRule = useMutation({
    mutationFn: () => {
      const parameters: Record<string, unknown> = { column };
      if (expectationType === "min" || expectationType === "max") {
        parameters.value = Number(value);
      } else if (expectationType === "regex") {
        parameters.pattern = value;
      } else if (expectationType === "allowed_values") {
        parameters.values = value.split(",").map((v) => v.trim());
      }
      return api.addQualityRule(datasetId, expectationType, parameters, severity);
    },
    onSuccess: () => {
      setColumn("");
      setValue("");
      queryClient.invalidateQueries({ queryKey: ["quality-rules", datasetId] });
    },
  });

  const deleteRule = useMutation({
    mutationFn: (ruleId: string) => api.deleteQualityRule(datasetId, ruleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["quality-rules", datasetId] }),
  });

  const needsValue = ["min", "max", "regex", "allowed_values"].includes(expectationType);

  return (
    <section>
      <h2>Data quality</h2>
      <form
        className="inline-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          addRule.mutate();
        }}
      >
        <select value={expectationType} onChange={(e) => setExpectationType(e.target.value as ExpectationType)}>
          {EXPECTATION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input placeholder="column" value={column} onChange={(e) => setColumn(e.target.value)} required />
        {needsValue && (
          <input
            placeholder={expectationType === "allowed_values" ? "comma-separated values" : "value"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
        )}
        <select value={severity} onChange={(e) => setSeverity(e.target.value as "warning" | "blocking")}>
          <option value="blocking">blocking</option>
          <option value="warning">warning</option>
        </select>
        <button type="submit" disabled={addRule.isPending}>
          Add rule
        </button>
      </form>
      <ErrorBanner error={addRule.error} />

      <ul className="card-list">
        {rules?.map((rule) => (
          <li key={rule.id} className="card rule-card">
            <code>{rule.expectation_type}</code> on <code>{String(rule.parameters.column)}</code>{" "}
            <StatusBadge value={rule.severity} />
            <button onClick={() => deleteRule.mutate(rule.id)}>Remove</button>
          </li>
        ))}
      </ul>

      <h3>Run history</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Outcome</th>
            <th>When</th>
            <th>Job</th>
          </tr>
        </thead>
        <tbody>
          {runs?.map((run) => (
            <tr key={run.id}>
              <td>
                <StatusBadge value={run.outcome} />
              </td>
              <td>{new Date(run.created_at).toLocaleString()}</td>
              <td>{run.job_id ?? "—"}</td>
            </tr>
          ))}
          {runs?.length === 0 && (
            <tr>
              <td colSpan={3} className="muted">
                No quality runs yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

function LineageSection({ datasetId }: { datasetId: string }) {
  const { data: lineage } = useQuery({
    queryKey: ["lineage", datasetId],
    queryFn: () => api.getDatasetLineage(datasetId),
  });

  return (
    <section>
      <h2>Lineage</h2>
      <h3>Upstream (what produced this dataset)</h3>
      <ul>
        {lineage?.upstream.map((edge) => (
          <li key={edge.id}>
            {edge.from_entity_type}:{edge.from_entity_id}
          </li>
        ))}
        {lineage?.upstream.length === 0 && <li className="muted">Nothing recorded yet.</li>}
      </ul>
      <h3>Downstream (what this dataset feeds)</h3>
      <ul>
        {lineage?.downstream.map((edge) => (
          <li key={edge.id}>
            {edge.to_entity_type}:{edge.to_entity_id}
          </li>
        ))}
        {lineage?.downstream.length === 0 && <li className="muted">Nothing consumes this dataset yet.</li>}
      </ul>
    </section>
  );
}

function QuerySection({ datasetId }: { datasetId: string }) {
  const [sql, setSql] = useState("SELECT * FROM dataset LIMIT 100");
  const runQuery = useMutation({ mutationFn: () => api.runQuery(datasetId, sql) });

  return (
    <section>
      <h2>Query</h2>
      <form
        className="query-form"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          runQuery.mutate();
        }}
      >
        <textarea value={sql} onChange={(e) => setSql(e.target.value)} rows={3} />
        <button type="submit" disabled={runQuery.isPending}>
          {runQuery.isPending ? "Running..." : "Run query"}
        </button>
      </form>
      <ErrorBanner error={runQuery.error} />

      {runQuery.data && (
        <table className="data-table">
          <thead>
            <tr>
              {runQuery.data.columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runQuery.data.rows.map((row, i) => (
              <tr key={i}>
                {runQuery.data!.columns.map((c) => (
                  <td key={c}>{String(row[c])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function DatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  if (!datasetId) return null;

  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId),
  });

  return (
    <div className="page">
      <h1>{dataset?.name}</h1>
      <p className="muted">
        Layer: {dataset?.layer} · Status: <StatusBadge value={dataset?.status} /> ·{" "}
        {dataset?.physical_location}
      </p>

      <SchemaSection datasetId={datasetId} />
      <TagsAndClassificationSection datasetId={datasetId} />
      <QualitySection datasetId={datasetId} />
      <LineageSection datasetId={datasetId} />
      <QuerySection datasetId={datasetId} />
    </div>
  );
}
