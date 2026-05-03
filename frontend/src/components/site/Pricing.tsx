import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const plans = [
  {
    name: "Bookkeeping Only",
    price: "149",
    suffix: "/ mo",
    desc: "Flat-rate double-entry bookkeeping for owner-operators and small fleets.",
    features: [
      "Unlimited transactions",
      "Auto-categorization",
      "P&L, balance sheet, cash flow",
      "1099 + tax export",
      "API + dashboard access",
    ],
    cta: "Start bookkeeping",
    highlight: false,
  },
  {
    name: "Combo",
    price: "249",
    suffix: "+ $9 / worker",
    desc: "Payroll + bookkeeping in one ledger. The full stack for growing carriers.",
    features: [
      "Everything in Payroll & Bookkeeping",
      "Unified general ledger",
      "Settlement → ledger automation",
      "Priority support · 4hr SLA",
      "Dedicated success engineer",
    ],
    cta: "Start free trial",
    highlight: true,
  },
  {
    name: "Payroll Only",
    price: "189",
    suffix: "+ $7 / driver",
    desc: "Settlements, payouts, and tax forms — without the bookkeeping module.",
    features: [
      "Driver + contractor settlements",
      "Stripe payout integration",
      "1099 / W-2 generation",
      "Webhook event stream",
      "Email + chat support",
    ],
    cta: "Start payroll",
    highlight: false,
  },
];

export const Pricing = () => {
  const navigate = useNavigate();

  return (
    <section id="pricing" className="relative py-32 overflow-hidden">
      <div className="absolute inset-0 bg-radial-glow opacity-60" />
      <div className="container relative mx-auto px-6">

        {/* Header — centered */}
        <div className="max-w-2xl mx-auto text-center mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-5 text-xs font-mono"
            style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" }}>
            <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
            PRICING
          </div>
          <h2 className="text-4xl sm:text-5xl font-semibold tracking-tight text-white mb-5">
            Predictable pricing. No surprise fees.
          </h2>
          <p className="text-lg text-muted-foreground">
            Stripe-managed subscriptions with transparent per-worker billing.
            Cancel or scale at any time.
          </p>
        </div>

        {/* 3 cards */}
        <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {plans.map((p) => (
            <div
              key={p.name}
              className={cn(
                "relative rounded-2xl border p-8 flex flex-col",
                p.highlight
                  ? "border-primary/50 bg-surface"
                  : "border-border bg-surface/50",
              )}
              style={p.highlight ? { boxShadow: "0 0 60px -15px rgba(54,211,148,0.4)" } : {}}
            >
              {p.highlight && (
                <>
                  <div className="absolute -inset-px rounded-2xl -z-10 blur-sm"
                    style={{ background: "linear-gradient(to bottom, rgba(54,211,148,0.4), transparent)" }} />
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap"
                    style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
                    MOST POPULAR
                  </span>
                </>
              )}

              <h3 className="text-white font-semibold text-lg">{p.name}</h3>
              <p className="text-sm text-muted-foreground mt-1.5 mb-6 min-h-[40px]">{p.desc}</p>

              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-5xl font-semibold text-white tracking-tight">${p.price}</span>
                <span className="text-muted-foreground text-sm">{p.suffix}</span>
              </div>

              <Button
                size="lg"
                className="w-full mb-8 font-medium"
                style={p.highlight
                  ? { background: "rgb(54,211,148)", color: "rgb(14,20,27)", boxShadow: "0 0 30px rgba(54,211,148,0.3)" }
                  : { background: "transparent", border: "1px solid rgb(33,42,54)", color: "rgb(183,197,215)" }
                }
                onClick={() => navigate("/register")}
              >
                {p.cta}
              </Button>

              <ul className="space-y-3 text-sm">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5">
                    <Check size={16} className="mt-0.5 flex-shrink-0" style={{ color: "rgb(54,211,148)" }} />
                    <span className="text-foreground/90">{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-10 font-mono">
          All plans · 14-day trial · No credit card required · Cancel anytime
        </p>
      </div>
    </section>
  );
};