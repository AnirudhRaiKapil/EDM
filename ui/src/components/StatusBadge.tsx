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
  critical: "status-bad",
  open: "status-warning",
  acknowledged: "status-pending",
  resolved: "status-good",
  draft: "status-pending",
  promoted: "status-good",
  ok: "status-good",
  error: "status-bad",
  skipped: "status-warning",
};

export function StatusBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  return <span className={`status-badge ${TONE[value] ?? ""}`}>{value}</span>;
}
