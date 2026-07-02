import { Check, Minus, X } from "lucide-react";
import { Reveal } from "./Reveal";

type Mark = "yes" | "partial" | "no";

const rows: { feature: string; lh: Mark; general: Mark; trucking: Mark }[] = [
  { feature: "Per-mile, per-load & percentage pay", lh: "yes", general: "no", trucking: "yes" },
  { feature: "Fuel advances, escrow & IFTA deductions", lh: "yes", general: "no", trucking: "partial" },
  { feature: "Direct-deposit driver payouts", lh: "yes", general: "yes", trucking: "no" },
  { feature: "1099-NEC filing", lh: "yes", general: "yes", trucking: "no" },
  { feature: "Double-entry books tied to settlements", lh: "yes", general: "no", trucking: "no" },
  { feature: "Audit trail on every transaction", lh: "yes", general: "partial", trucking: "no" },
];

const MarkIcon = ({ mark }: { mark: Mark }) => {
  if (mark === "yes")
    return <Check size={18} strokeWidth={2.5} className="text-primary mx-auto" aria-label="Yes" />;
  if (mark === "partial")
    return (
      <Minus
        size={18}
        strokeWidth={2.5}
        className="text-muted-foreground mx-auto"
        aria-label="Partial"
      />
    );
  return (
    <X
      size={18}
      strokeWidth={2}
      className="text-[hsl(var(--muted-foreground)/0.45)] mx-auto"
      aria-label="No"
    />
  );
};

export const Compare = () => (
  <section id="compare" className="py-24 lg:py-32">
    <div className="max-w-5xl mx-auto px-6">
      <Reveal>
        <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tighter leading-[1.08] max-w-2xl">
          Why carriers switch from generic payroll.
        </h2>
        <p className="mt-5 text-lg text-muted-foreground leading-relaxed max-w-[36rem]">
          General payroll software can cut a check. It cannot read a rate
          confirmation, hold escrow, or settle a load.
        </p>
      </Reveal>

      <Reveal delay={120}>
        <div className="mt-12 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                <th className="text-left pb-4 pr-4 font-semibold text-sm text-muted-foreground w-[40%]">
                  What your fleet needs
                </th>
                <th className="pb-4 px-4 w-[20%]">
                  <span className="inline-block rounded-full bg-primary text-primary-foreground text-sm font-bold px-4 py-1.5">
                    LedgerHaul
                  </span>
                </th>
                <th className="pb-4 px-4 w-[20%]">
                  <p className="font-bold text-sm">General payroll</p>
                  <p className="text-xs text-muted-foreground font-normal mt-0.5">
                    Gusto, OnPay, QuickBooks
                  </p>
                </th>
                <th className="pb-4 px-4 w-[20%]">
                  <p className="font-bold text-sm">Trucking tools</p>
                  <p className="text-xs text-muted-foreground font-normal mt-0.5">
                    RigBooks, TruckingOffice
                  </p>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.feature}>
                  <td className="py-4 pr-4 text-[15px] font-medium">{r.feature}</td>
                  <td className="py-4 px-4 text-center bg-[hsl(var(--primary)/0.05)]">
                    <MarkIcon mark={r.lh} />
                  </td>
                  <td className="py-4 px-4 text-center">
                    <MarkIcon mark={r.general} />
                  </td>
                  <td className="py-4 px-4 text-center">
                    <MarkIcon mark={r.trucking} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>
    </div>
  </section>
);
