import type { DashboardSummary } from "../types";

interface Props {
  summary: DashboardSummary;
}

export function SummaryCards({ summary }: Props) {
  const cells = [
    { label: "Resident reports", value: summary.reports, hint: "Raw submissions" },
    { label: "Consolidated incidents", value: summary.incidents, hint: "After dedup" },
    {
      label: "High / critical",
      value: summary.high_or_critical,
      hint: "Needs attention first",
      signal: "critical" as const,
    },
    {
      label: "Needs review",
      value: summary.needs_review,
      hint: "Uncertain / unsupported",
      signal: "review" as const,
    },
  ];

  return (
    <section className="status-strip" aria-label="Dashboard summary">
      {cells.map((cell) => (
        <div className="status-cell" key={cell.label}>
          <span className="status-label">{cell.label}</span>
          <strong className="status-value" data-signal={cell.signal}>
            {cell.value}
          </strong>
          <span className="status-hint">{cell.hint}</span>
        </div>
      ))}
    </section>
  );
}
