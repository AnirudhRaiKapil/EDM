const TONE: Record<string, string> = {
  succeeded: "status-good",
  passed: "status-good",
  active: "status-good",
  available: "status-good",
  running: "status-pending",
  queued: "status-pending",
  passed_with_warnings: "status-warning",
  warning: "status-warning",
  failed: "status-bad",
  blocking: "status-bad",
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  return <span className={`status-badge ${TONE[value] ?? ""}`}>{value}</span>;
}
