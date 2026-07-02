import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import {
  DollarSign, BookOpen, Users, FileText,
  TrendingUp, CreditCard, ArrowUpRight, Loader2,
} from "lucide-react";

interface RunSummary {
  id: number;
  status?: string;
  pay_date?: string;
  gross_total?: string;
  net_total?: string;
  payload?: { contractors?: unknown[] } | null;
}

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const quickActions = [
  { label: "Add Contractors",   desc: "Onboard the drivers and contractors you pay",   icon: Users,      to: "/settlements" },
  { label: "Run Payroll",       desc: "Create and submit a contractor payroll run",     icon: DollarSign, to: "/payroll"     },
  { label: "Set Up Your Books", desc: "Seed your chart of accounts and review ledger",  icon: BookOpen,   to: "/bookkeeping" },
  { label: "Generate Reports",  desc: "P&L, balance sheet, trial balance, cash flow",   icon: FileText,   to: "/reports"     },
];

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [contractorCount, setContractorCount] = useState<number | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [accountCount, setAccountCount] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [cRes, rRes, aRes] = await Promise.allSettled([
        apiFetch("/api/contractors"),
        apiFetch("/payroll/runs"),
        apiFetch("/coa/accounts"),
      ]);
      if (!alive) return;
      if (cRes.status === "fulfilled" && cRes.value.ok) {
        const d = await cRes.value.json().catch(() => null);
        setContractorCount(Array.isArray(d?.contractors) ? d.contractors.length : 0);
      }
      if (rRes.status === "fulfilled" && rRes.value.ok) {
        const d = await rRes.value.json().catch(() => null);
        setRuns(Array.isArray(d?.runs) ? d.runs : []);
      }
      if (aRes.status === "fulfilled" && aRes.value.ok) {
        const d = await aRes.value.json().catch(() => null);
        setAccountCount(Array.isArray(d) ? d.length : 0);
      }
      setLoading(false);
    })();
    return () => { alive = false; };
  }, []);

  const lastRun = runs[0];
  const ytdNet = runs.reduce((sum, r) => sum + (Number(r.net_total) || 0), 0);

  const stats = [
    { label: "Active Contractors", value: contractorCount ?? "—", sub: "on your roster", icon: Users },
    { label: "Payroll Runs", value: runs.length, sub: "all time", icon: CreditCard },
    { label: "Last Run Net", value: lastRun ? money(lastRun.net_total) : "—", sub: lastRun?.status ? `status: ${lastRun.status}` : "no runs yet", icon: DollarSign },
    { label: "Total Net Paid", value: money(ytdNet), sub: "across all runs", icon: TrendingUp },
  ];

  return (
    <AppLayout active="Dashboard">
      <div className="max-w-6xl">
        <div className="mb-8">
          <h1 className="text-2xl font-extrabold tracking-tight mb-1">
            Welcome back, {user?.first_name} 👋
          </h1>
          <p className="text-muted-foreground">
            Here's what's happening with your operations today.
          </p>
        </div>

        {/* Stats grid */}
        {loading ? (
          <div className="flex items-center gap-3 text-muted-foreground py-10 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading your data…
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
            {stats.map((s) => (
              <div key={s.label} className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">{s.label}</span>
                  <s.icon size={16} className="text-primary" />
                </div>
                <div className="text-2xl font-extrabold tracking-tight mb-1">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.sub}</div>
              </div>
            ))}
          </div>
        )}

        {/* Getting started nudge */}
        {!loading && contractorCount === 0 && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 mb-8 flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex-1">
              <div className="font-semibold mb-0.5">Get set up in two steps</div>
              <p className="text-sm text-muted-foreground">
                Add your first contractor, then run your first settlement — it takes about five minutes.
              </p>
            </div>
            <button
              onClick={() => navigate("/settlements")}
              className="rounded-full bg-primary text-primary-foreground text-sm font-semibold px-5 py-2.5 hover:bg-[hsl(var(--primary-dim))] transition-colors self-start sm:self-auto"
            >
              Add a contractor
            </button>
          </div>
        )}

        {/* Quick actions */}
        <h2 className="text-lg font-bold mb-4">Quick Actions</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          {quickActions.map((a) => (
            <button
              key={a.label}
              onClick={() => navigate(a.to)}
              className="group rounded-2xl border border-border bg-card p-5 text-left hover:border-primary/50 hover:shadow-md transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="h-10 w-10 rounded-lg flex items-center justify-center mb-3 bg-primary/10 border border-primary/20">
                  <a.icon size={18} className="text-primary" />
                </div>
                <ArrowUpRight size={16} className="text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
              <div className="font-semibold mb-1">{a.label}</div>
              <div className="text-sm text-muted-foreground">{a.desc}</div>
            </button>
          ))}
        </div>
      </div>
    </AppLayout>
  );
};

export default Dashboard;
