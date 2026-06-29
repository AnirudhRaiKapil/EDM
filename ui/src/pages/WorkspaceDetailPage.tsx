import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import * as api from "../api/endpoints";
import { ErrorBanner } from "../components/ErrorBanner";
import { useAuth } from "../context/AuthContext";

export function WorkspaceDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  if (!workspaceId) return null;
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: workspace } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => api.getWorkspace(workspaceId),
  });
  const { data: projects } = useQuery({
    queryKey: ["projects", workspaceId],
    queryFn: () => api.listProjects(workspaceId),
  });
  const { data: members } = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api.listMembers(workspaceId),
  });
  const isOwner = members?.some((m) => m.email === user?.email && m.role_name === "owner") ?? false;
  const { data: auditEvents } = useQuery({
    queryKey: ["audit-events", workspaceId],
    queryFn: () => api.listWorkspaceAuditEvents(workspaceId),
    enabled: isOwner,
  });

  const [projectName, setProjectName] = useState("");
  const [environment, setEnvironment] = useState("dev");
  const createProject = useMutation({
    mutationFn: () => api.createProject(workspaceId, projectName, environment),
    onSuccess: () => {
      setProjectName("");
      queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] });
    },
  });

  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<"owner" | "member">("member");
  const addMember = useMutation({
    mutationFn: () => api.addMember(workspaceId, memberEmail, memberRole),
    onSuccess: () => {
      setMemberEmail("");
      queryClient.invalidateQueries({ queryKey: ["members", workspaceId] });
    },
  });

  return (
    <div className="page">
      <Link to="/workspaces" className="back-link">
        &larr; Workspaces
      </Link>
      <h1>{workspace?.name}</h1>
      <p className="muted">{workspace?.description}</p>

      <section>
        <h2>Projects</h2>
        <form
          className="inline-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            createProject.mutate();
          }}
        >
          <input
            placeholder="Project name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            required
          />
          <select value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            <option value="dev">dev</option>
            <option value="qa">qa</option>
            <option value="uat">uat</option>
            <option value="prod">prod</option>
          </select>
          <button type="submit" disabled={createProject.isPending}>
            Create project
          </button>
        </form>
        <ErrorBanner error={createProject.error} />

        <ul className="card-list">
          {projects?.map((project) => (
            <li key={project.id} className="card">
              <Link to={`/workspaces/${workspaceId}/projects/${project.id}`}>
                <strong>{project.name}</strong>
                <span className="muted"> — {project.environment}</span>
              </Link>
            </li>
          ))}
          {projects?.length === 0 && <p className="muted">No projects yet.</p>}
        </ul>
      </section>

      <section>
        <h2>Members</h2>
        <form
          className="inline-form"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            addMember.mutate();
          }}
        >
          <input
            type="email"
            placeholder="user@example.com"
            value={memberEmail}
            onChange={(e) => setMemberEmail(e.target.value)}
            required
          />
          <select value={memberRole} onChange={(e) => setMemberRole(e.target.value as "owner" | "member")}>
            <option value="member">member</option>
            <option value="owner">owner</option>
          </select>
          <button type="submit" disabled={addMember.isPending}>
            Add member
          </button>
        </form>
        <ErrorBanner error={addMember.error} />

        <table className="data-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {members?.map((m) => (
              <tr key={m.user_id}>
                <td>{m.email}</td>
                <td>{m.role_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {isOwner && (
        <section>
          <h2>Audit Log</h2>
          <p className="muted">Owner-only: who did what, and when, in this workspace.</p>
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Subject</th>
              </tr>
            </thead>
            <tbody>
              {auditEvents?.map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.created_at).toLocaleString()}</td>
                  <td>{event.action}</td>
                  <td>{event.entity_type ? `${event.entity_type}:${event.entity_id ?? ""}` : "—"}</td>
                  <td>{event.subject_email ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {auditEvents?.length === 0 && <p className="muted">No audit events yet.</p>}
        </section>
      )}
    </div>
  );
}
