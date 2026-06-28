import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";

export function WorkspacesPage() {
  const queryClient = useQueryClient();
  const { data: workspaces, isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: api.listWorkspaces,
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const createMutation = useMutation({
    mutationFn: () => api.createWorkspace(name, description),
    onSuccess: () => {
      setName("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="page">
      <h1>Workspaces</h1>

      <form className="inline-form" onSubmit={handleSubmit}>
        <input
          placeholder="Workspace name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button type="submit" disabled={createMutation.isPending}>
          Create workspace
        </button>
      </form>
      <ErrorBanner error={createMutation.error} />

      {isLoading && <p>Loading...</p>}
      <ul className="card-list">
        {workspaces?.map((ws) => (
          <li key={ws.id} className="card">
            <Link to={`/workspaces/${ws.id}`}>
              <strong>{ws.name}</strong>
              <span className="muted"> — {ws.description || "no description"}</span>
            </Link>
          </li>
        ))}
        {workspaces?.length === 0 && <p className="muted">No workspaces yet — create one above.</p>}
      </ul>
    </div>
  );
}
