import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, CreditCard, CheckCircle, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BillingInfo {
  plan?: string;
  status?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
  stripe_customer_id?: string;
  portal_url?: string;
  [key: string]: unknown;
}

const PLANS = [
  {
    name: "Starter",
    price: "$49",
    period: "/mo",
    features: ["Up to 10 drivers", "Settlements & payroll", "Chart of accounts", "Email support"],
  },
  {
    name: "Growth",
    price: "$149",
    period: "/mo",
    features: ["Up to 50 drivers", "Everything in Starter", "Financial reports", "Priority support", "API access"],
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    features: ["Unlimited drivers", "Everything in Growth", "Dedicated onboarding", "SLA & custom contracts"],
  },
];

const fmtDate = (s?: string) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : "—";

const Billing = () => {
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/billing/status");
      if (res.ok) {
        const data = await res.json();
        setInfo(data.billing || data);
      }
    } catch {
      // billing endpoint may not exist yet — that's fine
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await apiFetch("/billing/portal", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.url) window.open(data.url, "_blank");
      } else {
        setError("Could not open billing portal. Please try again.");
      }
    } catch {
      setError("Network error.");
    }
    setPortalLoading(false);
  };

  const hasActivePlan = info?.plan && info?.status === "active";

  return (
    <AppLayout active="Billing">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white">Billing & Plans</h1>
            <p className="text-muted-foreground mt-1">Manage your subscription and payment details</p>
          </div>
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded-xl text-sm mb-6" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {/* Current plan card */}
        {!loading && hasActivePlan && (
          <div className="rounded-xl border p-6 mb-8 flex items-start justify-between"
            style={{ background: "rgba(54,211,148,0.05)", borderColor: "rgba(54,211,148,0.3)" }}>
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full flex items-center justify-center"
                style={{ background: "rgba(54,211,148,0.15)", border: "1px solid rgba(54,211,148,0.3)" }}>
                <CreditCard size={20} style={{ color: "rgb(54,211,148)" }} />
              </div>
              <div>
                <div className="text-white font-semibold">{info?.plan} Plan</div>
                <div className="text-sm text-muted-foreground mt-0.5">
                  Renews {fmtDate(info?.current_period_end)}
                  {info?.cancel_at_period_end && " · Cancels at end of period"}
                </div>
              </div>
            </div>
            <Button onClick={handlePortal} disabled={portalLoading} size="sm"
              style={{ background: "rgba(54,211,148,0.15)", color: "rgb(54,211,148)", border: "1px solid rgba(54,211,148,0.3)" }}>
              {portalLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : <ExternalLink size={14} className="mr-1" />}
              Manage Subscription
            </Button>
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-10 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading billing info…
          </div>
        )}

        {/* Plan cards */}
        <h2 className="text-lg font-semibold text-white mb-4">
          {hasActivePlan ? "Available Plans" : "Choose a Plan"}
        </h2>
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className="rounded-xl border p-6 flex flex-col"
              style={{
                background: plan.highlighted ? "rgba(54,211,148,0.05)" : "rgba(19,27,37,0.6)",
                borderColor: plan.highlighted ? "rgba(54,211,148,0.4)" : "var(--border)",
              }}
            >
              {plan.highlighted && (
                <div className="text-xs font-semibold uppercase tracking-widest mb-3 px-2 py-0.5 rounded self-start"
                  style={{ background: "rgba(54,211,148,0.15)", color: "rgb(54,211,148)" }}>
                  Most Popular
                </div>
              )}
              <div className="text-white font-semibold text-lg mb-1">{plan.name}</div>
              <div className="mb-4">
                <span className="text-3xl font-bold text-white">{plan.price}</span>
                <span className="text-muted-foreground text-sm">{plan.period}</span>
              </div>
              <ul className="flex-1 space-y-2 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle size={14} style={{ color: "rgb(54,211,148)", flexShrink: 0 }} />
                    {f}
                  </li>
                ))}
              </ul>
              <Button
                className="w-full"
                onClick={() => plan.name === "Enterprise" ? window.open("mailto:sales@ledgerhaul.com") : handlePortal()}
                disabled={portalLoading}
                style={
                  plan.highlighted
                    ? { background: "rgb(54,211,148)", color: "rgb(14,20,27)" }
                    : {}
                }
                variant={plan.highlighted ? "default" : "outline"}
              >
                {plan.name === "Enterprise" ? "Contact Sales" : portalLoading ? <Loader2 size={14} className="animate-spin" /> : "Get Started"}
              </Button>
            </div>
          ))}
        </div>

        {/* Info note */}
        <p className="text-xs text-muted-foreground text-center">
          Billing is handled securely via Stripe. No card data is stored on our servers.
          Questions? Email <span style={{ color: "rgb(54,211,148)" }}>support@ledgerhaul.com</span>
        </p>
      </div>
    </AppLayout>
  );
};

export default Billing;
