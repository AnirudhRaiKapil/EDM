import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { CatalogPage } from "./pages/CatalogPage";
import { DatasetDetailPage } from "./pages/DatasetDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { NotebookDetailPage } from "./pages/NotebookDetailPage";
import { PipelineDetailPage } from "./pages/PipelineDetailPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { RegisterPage } from "./pages/RegisterPage";
import { WorkspaceDetailPage } from "./pages/WorkspaceDetailPage";
import { WorkspacesPage } from "./pages/WorkspacesPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/workspaces" replace />} />
          <Route path="/workspaces" element={<WorkspacesPage />} />
          <Route path="/workspaces/:workspaceId" element={<WorkspaceDetailPage />} />
          <Route
            path="/workspaces/:workspaceId/projects/:projectId"
            element={<ProjectDetailPage />}
          />
          <Route path="/pipelines/:pipelineId" element={<PipelineDetailPage />} />
          <Route path="/notebooks/:notebookId" element={<NotebookDetailPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
