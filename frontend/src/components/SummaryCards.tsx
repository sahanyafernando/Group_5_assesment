import type { DashboardSummary } from "../types";

interface Props {
  summary: DashboardSummary;
}

export function SummaryCards({ summary }: Props) {
  const cards = [
    { label: "Resident reports", value: summary.reports, hint: "Raw submissions" },
    { label: "Real incidents", value: summary.incidents, hint: "Consolidated problems" },
    {
      label: "High / critical",
      value: summary.high_or_critical,
      hint: "Needs attention first",
    },
    {
      label: "Needs review",
      value: summary.needs_review,
      hint: "Uncertain / unsupported",
    },
  ];

  return (
    <section className="summary-grid" aria-label="Dashboard summary">
      {cards.map((card) => (
        <article className="summary-card" key={card.label}>
          <span className="summary-label">{card.label}</span>
          <strong>{card.value}</strong>
          <small>{card.hint}</small>
        </article>
      ))}
    </section>
  );
}
