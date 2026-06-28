import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { StatusBadge } from "../components/StatusBadge";
import type { CellRunResult, NotebookCell } from "../api/types";

function CellEditor({
  cell,
  result,
  onRunUpToHere,
  isRunning,
}: {
  cell: NotebookCell;
  result?: CellRunResult;
  onRunUpToHere: () => void;
  isRunning: boolean;
}) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState(cell.code);

  useEffect(() => setCode(cell.code), [cell.code]);

  const save = useMutation({
    mutationFn: (newCode: string) => api.updateNotebookCell(cell.notebook_id, cell.id, newCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notebook", cell.notebook_id] }),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteNotebookCell(cell.notebook_id, cell.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notebook", cell.notebook_id] }),
  });

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <textarea
        rows={4}
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onBlur={() => {
          if (code !== cell.code) save.mutate(code);
        }}
        style={{ width: "100%", fontFamily: "ui-monospace, Consolas, monospace" }}
      />
      <div className="inline-form" style={{ marginTop: 8, marginBottom: 0 }}>
        <button onClick={onRunUpToHere} disabled={isRunning}>
          Run up to here
        </button>
        <button onClick={() => remove.mutate()}>Delete cell</button>
        {result && <StatusBadge value={result.status} />}
      </div>
      {result && (
        <div style={{ marginTop: 8 }}>
          {result.stdout && <pre className="muted">{result.stdout}</pre>}
          {result.error && <div className="error-banner">{result.error}</div>}
          {result.status === "ok" && result.preview.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  {result.columns?.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.slice(0, 10).map((row, i) => (
                  <tr key={i}>
                    {result.columns?.map((c) => (
                      <td key={c}>{String(row[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.status === "ok" && (
            <p className="muted">{result.row_count} row(s) total in this cell's output.</p>
          )}
        </div>
      )}
    </div>
  );
}

export function NotebookDetailPage() {
  const { notebookId } = useParams<{ notebookId: string }>();
  const navigate = useNavigate();
  if (!notebookId) return null;
  const queryClient = useQueryClient();

  const { data: notebook } = useQuery({
    queryKey: ["notebook", notebookId],
    queryFn: () => api.getNotebook(notebookId),
  });

  const [results, setResults] = useState<Record<string, CellRunResult>>({});

  const runAll = useMutation({
    mutationFn: () => api.runNotebook(notebookId),
    onSuccess: (cellResults) => {
      setResults(Object.fromEntries(cellResults.map((r) => [r.cell_id, r])));
    },
  });

  const runUpTo = useMutation({
    mutationFn: (cellId: string) => api.runNotebook(notebookId, cellId),
    onSuccess: (cellResults) => {
      setResults((prev) => ({
        ...prev,
        ...Object.fromEntries(cellResults.map((r) => [r.cell_id, r])),
      }));
    },
  });

  const addCell = useMutation({
    mutationFn: () => api.addNotebookCell(notebookId, "# write pandas code here; 'df' is in scope"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const [outputDatasetName, setOutputDatasetName] = useState("");
  const [outputLayer, setOutputLayer] = useState("silver");
  const promote = useMutation({
    mutationFn: () => api.promoteNotebook(notebookId, outputDatasetName, outputLayer),
    onSuccess: (pipeline) => navigate(`/pipelines/${pipeline.id}`),
  });

  return (
    <div className="page">
      <h1>{notebook?.name}</h1>
      <p className="muted">
        Sample size: {notebook?.sample_size} rows · <StatusBadge value={notebook?.status} />
        {notebook?.promoted_pipeline_id && (
          <>
            {" "}
            ·{" "}
            <a href={`/pipelines/${notebook.promoted_pipeline_id}`}>view promoted pipeline</a>
          </>
        )}
      </p>

      <div className="inline-form">
        <button onClick={() => runAll.mutate()} disabled={runAll.isPending}>
          {runAll.isPending ? "Running..." : "Run all cells"}
        </button>
        <button onClick={() => addCell.mutate()}>+ Add cell</button>
      </div>
      <ErrorBanner error={runAll.error} />

      {notebook?.cells.map((cell) => (
        <CellEditor
          key={cell.id}
          cell={cell}
          result={results[cell.id]}
          onRunUpToHere={() => runUpTo.mutate(cell.id)}
          isRunning={runUpTo.isPending}
        />
      ))}
      {notebook?.cells.length === 0 && <p className="muted">No cells yet — add one above.</p>}

      <section>
        <h2>Promote to a scheduled pipeline</h2>
        <p className="muted">
          Runs this exact code (concatenated across all cells) against the source's full data,
          as a regular Pipeline you can run on demand or put on a cron schedule.
        </p>
        <form
          className="inline-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            promote.mutate();
          }}
        >
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
          <button type="submit" disabled={promote.isPending || notebook?.cells.length === 0}>
            Promote
          </button>
        </form>
        <ErrorBanner error={promote.error} />
      </section>
    </div>
  );
}
