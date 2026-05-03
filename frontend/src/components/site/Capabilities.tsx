import { Check } from "lucide-react";

const checklist = [
  "Per-mile, per-load, % of revenue, and hybrid pay structures",
  "Automatic fuel advance reconciliation and IFTA deductions",
  "1099-NEC and W-2 export, year-round",
  "Idempotent calculations with full audit trail",
  "Webhook events on every settlement state change",
];

const lineItems = [
  { label: "Loaded miles · 2,227 mi", value: "+ $1,341.54", positive: true },
  { label: "Detention pay · 2 hrs",   value: "+ $90.00",    positive: true },
  { label: "Fuel advance",            value: "− $142.30",   positive: false },
  { label: "IFTA reserve",            value: "− $40.00",    positive: false },
  { label: "Insurance escrow",        value: "− $90.00",    positive: false },
];

export const Capabilities = () => {
  return (
    <section id="capabilities" className="relative py-32">
      <div className="container mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-20 items-center">

          {/* Left: copy + checklist */}
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-5 text-xs font-mono"
              style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" }}>
              <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
              SETTLEMENTS ENGINE
            </div>
            <h2 className="text-4xl sm:text-5xl font-semibold tracking-tight text-white mb-6">
              Contractor settlements, calculated correctly. Every time.
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Run per-mile, per-load, percentage, and salary models in the same call.
              Deduct fuel advances, IFTA, escrow, insurance, and post every cent to
              the ledger automatically.
            </p>
            <ul className="space-y-3">
              {checklist.map((t) => (
                <li key={t} className="flex items-start gap-3">
                  <div className="mt-0.5 h-5 w-5 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(54,211,148,0.15)", border: "1px solid rgba(54,211,148,0.4)" }}>
                    <Check size={12} style={{ color: "rgb(54,211,148)" }} strokeWidth={3} />
                  </div>
                  <span className="text-foreground/90">{t}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Right: settlement receipt card */}
          <div className="relative">
            <div className="absolute -inset-8 bg-primary/10 blur-3xl rounded-full" />
            <div className="relative rounded-2xl border border-border bg-surface overflow-hidden"
              style={{ boxShadow: "0 20px 60px -20px rgba(54,211,148,0.3)" }}>

              {/* Card header */}
              <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                <div>
                  <div className="text-xs text-muted-foreground font-mono">SETTLEMENT</div>
                  <div className="text-white font-semibold">#set_b9f3d2 · Week 17</div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: "rgba(54,211,148,0.15)", border: "1px solid rgba(54,211,148,0.4)", color: "rgb(54,211,148)" }}>
                  POSTED
                </span>
              </div>

              <div className="p-6 space-y-4">
                {/* Driver row */}
                <div className="flex justify-between items-baseline pb-4 border-b border-border">
                  <span className="text-muted-foreground text-sm">Driver</span>
                  <span className="text-white font-medium font-mono text-sm">Marcus Reyes · drv_7834A</span>
                </div>

                {/* Line items */}
                {lineItems.map(({ label, value, positive }) => (
                  <div key={label} className="flex justify-between items-baseline text-sm">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-mono" style={{ color: positive ? "rgb(54,211,148)" : "rgb(248,113,113)" }}>
                      {value}
                    </span>
                  </div>
                ))}

                {/* Net pay */}
                <div className="border-t border-border pt-4 flex justify-between items-baseline">
                  <span className="text-white font-medium">Net pay</span>
                  <span className="text-2xl font-semibold font-mono" style={{ color: "rgb(54,211,148)" }}>
                    $1,159.24
                  </span>
                </div>

                {/* Footer */}
                <div className="rounded-lg p-3 flex items-center gap-3 border border-border bg-surface-muted/60">
                  <div className="h-2 w-2 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
                  <div className="flex-1 text-xs text-muted-foreground">
                    Posted to <span className="text-white font-mono">stripe.po_1Q8xM2</span>
                  </div>
                  <span className="text-xs font-mono text-muted-foreground">42ms</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};