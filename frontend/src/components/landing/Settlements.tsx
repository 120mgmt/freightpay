import { Check } from "lucide-react";
import { Reveal } from "./Reveal";

/* Statement figures are sample data for illustration. */
const lines = [
  { label: "Linehaul", detail: "2,184 mi at $0.62 per mile", amount: "$1,354.08" },
  { label: "Detention", detail: "Stop 2, 3.0 hours", amount: "$150.00" },
  { label: "Fuel advance", detail: "Repaid this period", amount: "-$310.00" },
  { label: "Escrow", detail: "Weekly contribution", amount: "-$75.00" },
];

const points = [
  "Pay per mile, per load, percentage, or salary, set per driver",
  "Fuel advances, escrow, insurance, and IFTA deduct automatically",
  "Recalculate and reissue in seconds when a load changes",
];

export const Settlements = () => (
  <section id="how-it-works" className="py-24 lg:py-32">
    <div className="max-w-7xl mx-auto px-6">
      <div className="grid lg:grid-cols-12 gap-12 lg:gap-16 items-center">
        {/* Settlement statement preview (real product output, sample figures) */}
        <Reveal className="lg:col-span-6">
          <div className="rounded-2xl bg-[hsl(var(--primary)/0.06)] p-6 sm:p-10">
            <div className="rounded-2xl bg-card border border-border shadow-[0_18px_50px_-20px_hsl(200_35%_11%/0.25)] p-6 sm:p-8 max-w-md mx-auto">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-bold">Driver settlement</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    Marcus Reyes, May 26 to Jun 1
                  </p>
                </div>
                <span className="rounded-full bg-[hsl(var(--primary)/0.1)] text-primary text-xs font-semibold px-3 py-1">
                  Paid
                </span>
              </div>

              <div className="mt-6 space-y-4">
                {lines.map((l) => (
                  <div key={l.label} className="flex items-baseline justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold">{l.label}</p>
                      <p className="text-xs text-muted-foreground">{l.detail}</p>
                    </div>
                    <p
                      className={`text-sm font-semibold tabular-nums ${
                        l.amount.startsWith("-") ? "text-muted-foreground" : ""
                      }`}
                    >
                      {l.amount}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-5 border-t border-border flex items-baseline justify-between">
                <p className="font-bold">Net pay</p>
                <p className="text-xl font-extrabold tabular-nums">$1,119.08</p>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Posted to your ledger · direct deposit on Friday
              </p>
            </div>
          </div>
        </Reveal>

        {/* Copy */}
        <Reveal className="lg:col-span-6" delay={120}>
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tighter leading-[1.08]">
            Settlements your drivers stop calling about.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground leading-relaxed max-w-[34rem]">
            Every statement is itemized down to the load, so the Friday phone
            calls answer themselves.
          </p>
          <ul className="mt-8 space-y-4">
            {points.map((p) => (
              <li key={p} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--primary)/0.12)]">
                  <Check size={14} strokeWidth={2.5} className="text-primary" />
                </span>
                <span className="text-[15px] leading-relaxed">{p}</span>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </div>
  </section>
);
