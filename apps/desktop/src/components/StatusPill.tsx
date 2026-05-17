type StatusPillProps = {
  label: string;
  tone?: "good" | "warn" | "neutral";
};

export function StatusPill({ label, tone = "neutral" }: StatusPillProps) {
  return <span className={`status-pill ${tone}`}>{label}</span>;
}
