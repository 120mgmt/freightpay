import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { Reveal } from "./Reveal";

const plans = [
  {
    name: "Payroll Only",
    price: "$189",
    per: "/mo + $7 per driver",
    desc: "Settlements, payouts, and tax forms without the bookkeeping module.",
    features: [
      "Driver and contractor settlements",
      "Direct deposit payouts",
      "1099-NEC and W-2 generation",
      "Driver statement portal",
      "Email and chat support",
    ],
    highlight: false,
  },
  {
    name: "Combo",
    price: "$249",
    per: "/mo + $9 per worker",
    desc: "Payroll and bookkeeping in one ledger. The full stack for growing carriers.",
    features: [
      "Everything in Payroll and Bookkeeping",
      "Unified general ledger",
      "Settlements post to books automatically",
      "Priority support with 4-hour response",
      "Dedicated onboarding specialist",
    ],
    highlight: true,
  },
  {
    name: "Bookkeeping Only",
    price: "$149",
    per: "/mo flat",
    desc: "Flat-rate double-entry bookkeeping for owner-operators and small fleets.",
    features: [
      "Unlimited transactions",
      "Automatic categorization",
      "P&L, balance sheet, cash flow",
      "1099 and tax exports",
      "QuickBooks export",
    ],
    highlight: false,
  },
];

export const Pricing = () => {
  const navigate = useNavigate();

  return (
    <section id="pricing" className="py-24 lg:py-32 bg-surface border-y border-border">
      <div className="max-w-7xl mx-auto px-6">
        <Reveal className="text-center">
          <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tighter leading-[1.08]">
            Priced for fleets, not tech budgets.
          </h2>
          <p className="mt-5 text-lg text-muted-foreground leading-relaxed max-w-xl mx-auto">
            Every plan starts with a 14-day free trial. No setup fees, cancel anytime.
          </p>
        </Reveal>

        <div className="mt-14 grid md:grid-cols-3 gap-5 max-w-5xl mx-auto items-stretch">
          {plans.map((plan, i) => (
            <Reveal key={plan.name} delay={i * 90} className="h-full">
              <div
                className={`h-full flex flex-col rounded-2xl p-7 ${
                  plan.highlight
                    ? "bg-[hsl(var(--ink))] text-white shadow-[0_24px_60px_-24px_hsl(192_30%_8%/0.5)]"
                    : "bg-card border border-border"
                }`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg">{plan.name}</h3>
                  {plan.highlight && (
                    <span className="rounded-full bg-[hsl(var(--primary-glow)/0.18)] text-[hsl(var(--primary-glow))] text-xs font-semibold px-3 py-1">
                      Most popular
                    </span>
                  )}
                </div>
                <p
                  className={`mt-2 text-sm leading-relaxed ${
                    plan.highlight ? "text-white/75" : "text-muted-foreground"
                  }`}
                >
                  {plan.desc}
                </p>
                <div className="mt-6 flex items-baseline gap-1.5">
                  <span className="text-4xl font-extrabold tracking-tight tabular-nums">
                    {plan.price}
                  </span>
                  <span
                    className={`text-sm font-medium ${
                      plan.highlight ? "text-white/70" : "text-muted-foreground"
                    }`}
                  >
                    {plan.per}
                  </span>
                </div>
                <ul className="mt-7 space-y-3 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm leading-relaxed">
                      <Check
                        size={16}
                        strokeWidth={2.5}
                        className={`mt-0.5 shrink-0 ${
                          plan.highlight ? "text-[hsl(var(--primary-glow))]" : "text-primary"
                        }`}
                      />
                      <span className={plan.highlight ? "text-white/90" : ""}>{f}</span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => navigate("/register")}
                  className={`mt-8 w-full rounded-full text-sm font-semibold py-3 active:scale-[0.98] transition-all ${
                    plan.highlight
                      ? "bg-[hsl(var(--primary-glow))] text-[hsl(var(--ink))] hover:brightness-110"
                      : "bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]"
                  }`}
                >
                  Start free trial
                </button>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
};
