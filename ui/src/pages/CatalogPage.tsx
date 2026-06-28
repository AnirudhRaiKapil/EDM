import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../api/endpoints";

export function CatalogPage() {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get("project_id") ?? undefined;
  const [q, setQ] = useState("");

  const { data: datasets, isLoading } = useQuery({
    queryKey: ["catalog", projectId, q],
    queryFn: () => api.searchDatasets({ project_id: projectId, q: q || undefined }),
  });

  return (
    <div className="page">
      <h1>Catalog</h1>
      <input
        placeholder="Search dataset name..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="search-input"
      />

      {isLoading && <p>Loading...</p>}
      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Layer</th>
            <th>Status</th>
            <th>Classification</th>
          </tr>
        </thead>
        <tbody>
          {datasets?.map((d) => (
            <tr key={d.id}>
              <td>
                <Link to={`/datasets/${d.id}`}>{d.name}</Link>
              </td>
              <td>{d.layer}</td>
              <td>{d.status}</td>
              <td>{d.classification.join(", ") || "—"}</td>
            </tr>
          ))}
          {datasets?.length === 0 && (
            <tr>
              <td colSpan={4} className="muted">
                No datasets found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
