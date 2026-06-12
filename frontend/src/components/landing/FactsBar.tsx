import { Reveal } from "./Reveal";

const facts = [
  {
    label: "Four pay models",
    detail: "Per-mile, per-load, percentage, and salary",
  },
  {
    label: "Trucking deductions",
    detail: "Fuel advances, escrow, IFTA, insurance",
  },
  {
    label: "Year-end ready",
    detail: "1099-NEC and W-2 filing built in",
  },
  {
    label: "Books included",
    detail: "Double-entry ledger behind every settlement",
  },
];

export const FactsBar = () => (
  <section className="border-y border-border bg-surface">
    <Reveal>
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 lg:divide-x divide-border">
        {facts.map((f) => (
          <div key={f.label} className="py-7 lg:px-8 first:lg:pl-0 last:lg:pr-0">
            <p className="font-bold text-[15px]">{f.label}</p>
            <p className="mt-1 text-sm text-muted-foreground leading-snug">{f.detail}</p>
          </div>
        ))}
      </div>
    </Reveal>
  </section>
);
