import type { ReactNode } from "react";

export interface ObservationMetric {
  label: string;
  value: string;
  tone?: string;
}

export function ObservationMetricGrid({ dense = false, items }: { dense?: boolean; items: ObservationMetric[] }) {
  return (
    <div className={dense ? "observation-summary dense" : "observation-summary"}>
      {items.map((item) => (
        <ObservationMetricCard item={item} key={`${item.label}-${item.value}`} />
      ))}
    </div>
  );
}

export function ObservationMetricCard({ item }: { item: ObservationMetric }) {
  return (
    <div className={item.tone ? `observation-card ${item.tone}` : "observation-card"}>
      <span>{item.label}</span>
      <strong>{item.value}</strong>
    </div>
  );
}

export function ObservationSection({
  action,
  badge,
  children,
  className = "drawer-section",
  title,
}: {
  action?: ReactNode;
  badge?: string;
  children: ReactNode;
  className?: string;
  title: string;
}) {
  return (
    <section className={className}>
      <div className="section-heading">
        <h3>{title}</h3>
        {action || (badge !== undefined ? <span className="badge">{badge}</span> : null)}
      </div>
      {children}
    </section>
  );
}
