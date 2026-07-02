import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, CreditCard, CheckCircle, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BillingInfo {
  status?: string;
  plan?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
}

const PLANS = [
  {
    key: "payroll_only",
    name: "Payroll Only",
    price: "$189",
    period: "/mo + $7 per driver",
    features: [
      "Driver and contractor settlements",
      "Direct deposit payouts",
      "1099-NEC and W-2 generation",
      "Driver statement portal",
      "Email and chat support",
    ],
  },
  {
    key: "combo",
    name: "Combo",
    price: "$249",
    period: "/mo + $9 per worker",
    features: [
      "Everything in Payroll and Bookkeeping",
      "Unified general ledger",
      "Settlements post to books automatically",
      "Priority support with 4-hour response",
      "Dedicated onboarding specialist",
    ],
    highlighted: true,
  },
  {
    key: "bookkeeping_only",
    name: "Bookkeeping Only",
    price: "$149",
    period: "/mo flat",
    features: [
      "Unlimited transactions",
      "Automatic categorization",
      "P&L, balance sheet, cash flow",
      "1099 and tax exports",
      "QuickBooks export",
    ],
  },
];

const PLAN_NAMES: Record<string, string> = {
  payroll_only: "Payroll Only",
  combo: "Combo",
  bookkeeping_only: "Bookkeeping Only",
};

const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : "—";

const Billing = () => {
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/billing/status");
      if (res.ok) setInfo(await res.json());
    } catch {
      /* status is informational — plans below still work */
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCheckout = async (planKey: string) => {
    setBusyPlan(planKey);
    setError("");
    try {
      const res = await apiFetch("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan: planKey, employees: 0 }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      setError(data.detail || data.error || "Could not start checkout. Please try again.");
    } catch {
      setError("Network error — check your connection.");
    }
    setBusyPlan(null);
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    setError("");
    try {
      const res = await apiFetch("/billing/portal/session", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.url) {
        window.open(data.url, "_blank");
      } else {
        setError(data.detail || data.error || "Could not open the billing portal.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setPortalLoading(false);
  };

  const live = info && ["active", "trialing", "past_due"].includes(info.status || "");

  return (
    <AppLayout active="Billing">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Billing & Plans</h1>
            <p className="text-muted-foreground mt-1">Manage your subscription and payment details</p>
          </div>
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded-xl text-sm mb-6 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-10 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading billing info…
          </div>
        )}

        {/* Current plan card */}
        {!loading && live && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-6 mb-8 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full flex items-center justify-center bg-primary/10 border border-primary/25">
                <CreditCard size={20} className="text-primary" />
              </div>
              <div>
                <div className="font-bold">
                  {PLAN_NAMES[info?.plan || ""] || "Subscription"} · <span className="capitalize">{info?.status}</span>
                </div>
                <div className="text-sm text-muted-foreground mt-0.5">
                  Renews {fmtDate(info?.current_period_end)}
                  {info?.cancel_at_period_end && " · cancels at end of period"}
                </div>
              </div>
            </div>
            <Button onClick={handlePortal} disabled={portalLoading} size="sm" variant="outline"
              className="text-primary border-primary/40 hover:bg-primary/10 self-start">
              {portalLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : <ExternalLink size={14} className="mr-1" />}
              Manage Subscription
            </Button>
          </div>
        )}

        {/* Plan cards */}
        <h2 className="text-lg font-bold mb-4">{live ? "Change Plan" : "Choose a Plan"}</h2>
        <div className="grid md:grid-cols-3 gap-4 mb-8 items-stretch">
          {PLANS.map((plan) => {
            const isCurrent = live && info?.plan === plan.key;
            return (
              <div
                key={plan.key}
                className={`rounded-2xl border p-6 flex flex-col ${
                  plan.highlighted
                    ? "border-primary/40 bg-primary/5 shadow-md"
                    : "border-border bg-card shadow-sm"
                }`}
              >
                {plan.highlighted && (
                  <div className="text-xs font-bold uppercase tracking-widest mb-3 px-2 py-0.5 rounded self-start bg-primary/10 text-primary">
                    Most Popular
                  </div>
                )}
                <div className="font-bold text-lg mb-1">{plan.name}</div>
                <div className="mb-4">
                  <span className="text-3xl font-extrabold tracking-tight">{plan.price}</span>
                  <span className="text-muted-foreground text-sm"> {plan.period}</span>
                </div>
                <ul className="flex-1 space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <CheckCircle size={14} className="text-primary shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  className={`w-full ${plan.highlighted && !isCurrent ? "bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]" : ""}`}
                  variant={plan.highlighted && !isCurrent ? "default" : "outline"}
                  disabled={busyPlan !== null || isCurrent}
                  onClick={() => (isCurrent ? undefined : live ? handlePortal() : handleCheckout(plan.key))}
                >
                  {isCurrent
                    ? "Current Plan"
                    : busyPlan === plan.key
                      ? <Loader2 size={14} className="animate-spin" />
                      : live ? "Switch via Portal" : "Subscribe"}
                </Button>
              </div>
            );
          })}
        </div>

        <p className="text-xs text-muted-foreground text-center">
          Billing is handled securely via Stripe. No card data is stored on our servers.
          Questions? Email <a href="mailto:support@ledgerhaul.com" className="text-primary hover:underline">support@ledgerhaul.com</a>
        </p>
      </div>
    </AppLayout>
  );
};

export default Billing;
