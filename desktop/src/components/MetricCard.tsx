type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "accent" | "success" | "warning";
  icon?: React.ReactNode;
  compact?: boolean;
};

export function MetricCard({ label, value, hint, tone = "default", icon, compact }: MetricCardProps) {
  return (
    <div className={`metric-card ${tone}${compact ? " metric-card--compact" : ""}`}>
      {icon && <div className="metric-card-icon">{icon}</div>}
      <div className="metric-card-body">
        <span className="metric-card-value">{value}</span>
        <span className="metric-card-label">{label}</span>
        {hint ? <span className="metric-card-hint">{hint}</span> : null}
      </div>
    </div>
  );
}
