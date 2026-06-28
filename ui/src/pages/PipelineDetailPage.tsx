import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusBadge } from "../components/StatusBadge";

export function PipelineDetailPage() {
  const { pipelineId } = useParams<{ pipelineId: string }>();
  if (!pipelineId) return null;
  const queryClient = useQueryClient();

  const { data: pipeline } = useQuery({
    queryKey: ["pipeline", pipelineId],
    queryFn: () => api.getPipeline(pipelineId),
  });
  const { data: jobs } = useQuery({
    queryKey: ["jobs", pipelineId],
    queryFn: () => api.listJobs(pipelineId),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "running" || j.status === "queued") ? 1500 : false,
  });

  const runMutation = useMutation({
    mutationFn: () => api.runPipeline(pipelineId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs", pipelineId] }),
  });

  const [cron, setCron] = useState("");
  const setSchedule = useMutation({
    mutationFn: (value: string | null) => api.setPipelineSchedule(pipelineId, value),
    onSuccess: () => {
      setCron("");
      queryClient.invalidateQueries({ queryKey: ["pipeline", pipelineId] });
    },
  });

  return (
    <div className="page">
      <Link to="/workspaces" className="back-link">
        &larr; Workspaces
      </Link>
      <h1>{pipeline?.name}</h1>
      <p className="muted">
        Output: {pipeline?.output_dataset_name} ({pipeline?.output_layer}) · version {pipeline?.version}
      </p>

      <section>
        <h2>Transformations</h2>
        <ol>
          {pipeline?.transformations.map((t) => (
            <li key={t.id}>
              <code>{t.type}</code> {JSON.stringify(t.parameters)}
            </li>
          ))}
          {pipeline?.transformations.length === 0 && <p className="muted">No transformations — passthrough.</p>}
        </ol>
      </section>

      <section>
        <h2>Schedule</h2>
        {pipeline?.schedule_cron ? (
          <p>
            Runs on cron schedule <code>{pipeline.schedule_cron}</code>{" "}
            <button onClick={() => setSchedule.mutate(null)} disabled={setSchedule.isPending}>
              Clear schedule
            </button>
          </p>
        ) : (
          <p className="muted">Not scheduled — runs only on demand.</p>
        )}
        <form
          className="inline-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setSchedule.mutate(cron);
          }}
        >
          <input
            placeholder='Cron expression, e.g. "0 * * * *" (hourly)'
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            required
          />
          <button type="submit" disabled={setSchedule.isPending}>
            Set schedule
          </button>
        </form>
        <ErrorBanner error={setSchedule.error} />
      </section>

      <section>
        <button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
          {runMutation.isPending ? "Running..." : "Run pipeline"}
        </button>
        <ErrorBanner error={runMutation.error} />
      </section>

      <section>
        <h2>Job history</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Trigger</th>
              <th>Rows in/out</th>
              <th>Quality</th>
              <th>Started</th>
              <th>Dataset</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {jobs?.map((job) => (
              <tr key={job.id}>
                <td>
                  <StatusBadge value={job.status} />
                </td>
                <td>{job.trigger}</td>
                <td>
                  {job.metrics?.rowsIn ?? "—"} / {job.metrics?.rowsOut ?? "—"}
                </td>
                <td>
                  <StatusBadge value={job.metrics?.qualityOutcome ?? undefined} />
                </td>
                <td>{job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</td>
                <td>
                  {job.dataset_id ? (
                    <Link to={`/datasets/${job.dataset_id}`}>view</Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="error-cell">{job.error_message ?? ""}</td>
              </tr>
            ))}
            {jobs?.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
