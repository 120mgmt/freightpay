import { useCallback, useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type ReportType = "profit-and-loss" | "balance-sheet" | "trial-balance" | "cash-flow";

const TABS: { key: ReportType; label: string }[] = [
  { key: "profit-and-loss",  label: "Profit & Loss"  },
  { key: "balance-sheet",    label: "Balance Sheet"  },
  { key: "trial-balance",    label: "Trial Balance"  },
  { key: "cash-flow",        label: "Cash Flow"      },
];

interface Line { account_code?: string; name?: string; amount?: string; debit?: string; credit?: string; net?: string }
interface Section { total?: string; lines?: Line[] }
interface ReportData {
  lines?: Line[];
  totals?: { debit?: string; credit?: string; is_balanced?: boolean };
  revenue?: Section;
  expenses?: Section;
  assets?: Section;
  liabilities?: Section;
  equity?: Section;
  net_income?: string;
  operating_cash_flow?: string;
  investing_cash_flow?: string;
  financing_cash_flow?: string;
  net_change_in_cash?: string;
  is_balanced?: boolean;
  [key: string]: unknown;
}

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const thisMonth = () => new Date().toISOString().slice(0, 7);
const janThisYear = () => `${new Date().getFullYear()}-01`;

const SectionTable = ({ title, section }: { title: string; section?: Section }) => {
  if (!section) return null;
  const lines = section.lines || [];
  return (
    <div className="mb-6">
      <h2 className="text-xs font-bold uppercase tracking-widest mb-2 px-1 text-muted-foreground">{title}</h2>
      <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
        <table className="w-full text-sm">
          <tbody>
            {lines.length === 0 && (
              <tr><td className="px-4 py-3 text-muted-foreground">No activity in this period.</td></tr>
            )}
            {lines.map((l, i) => (
              <tr key={i} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground w-20">{l.account_code || ""}</td>
                <td className="px-4 py-2.5">{l.name || "—"}</td>
                <td className="px-4 py-2.5 text-right">{money(l.amount)}</td>
              </tr>
            ))}
            {section.total != null && (
              <tr className="bg-primary/5 border-t border-primary/20">
                <td className="px-4 py-2.5 font-bold" colSpan={2}>Total {title}</td>
                <td className="px-4 py-2.5 text-right font-bold text-primary">{money(section.total)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const StatCard = ({ label, value, accent = false }: { label: string; value: unknown; accent?: boolean }) => (
  <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
    <div className={`text-lg font-extrabold ${accent ? "text-primary" : ""}`}>{money(value)}</div>
  </div>
);

const Reports = () => {
  const [tab, setTab] = useState<ReportType>("profit-and-loss");
  const [from, setFrom] = useState(janThisYear());
  const [to, setTo] = useState(thisMonth());
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [needsPlan, setNeedsPlan] = useState(false);

  const load = useCallback(async (type: ReportType) => {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const qs = new URLSearchParams({ period_from: from, period_to: to });
      const res = await apiFetch(`/reporting/${type}?${qs}`);
      const json = await res.json().catch(() => ({}));
      if (res.status === 402 || json?.error === "plan_feature_unavailable") {
        setNeedsPlan(true);
      } else if (!res.ok) {
        setNeedsPlan(false);
        setError(json.error || `Failed to load ${type} report.`);
      } else {
        setNeedsPlan(false);
        setData(json);
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  }, [from, to]);

  useEffect(() => { load(tab); }, [tab, load]);

  return (
    <AppLayout active="Reports">
      <div className="max-w-5xl">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Financial Reports</h1>
            <p className="text-muted-foreground mt-1">Straight from your ledger — always current</p>
          </div>
          <div className="flex items-end gap-2">
            <div>
              <Label className="text-xs text-muted-foreground">From</Label>
              <Input type="month" className="mt-1 h-9 bg-surface" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">To</Label>
              <Input type="month" className="mt-1 h-9 bg-surface" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
            <Button variant="outline" size="sm" className="h-9" onClick={() => load(tab)}>
              <RefreshCw size={14} className="mr-1" /> Run
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl border border-border bg-surface overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 text-sm font-semibold py-2 px-3 rounded-lg whitespace-nowrap transition-colors ${
                tab === t.key
                  ? "bg-primary/10 text-primary border border-primary/25"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Building report…
          </div>
        )}

        {needsPlan && !loading && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-8 text-center">
            <h2 className="font-bold text-lg mb-2">Reports require an active plan</h2>
            <p className="text-muted-foreground mb-5 max-w-md mx-auto">
              Financial reports are part of bookkeeping. Subscribe to the
              <b> Bookkeeping Only</b> or <b>Combo</b> plan to unlock them.
            </p>
            <Link to="/billing">
              <Button className="rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))] px-6">
                Choose a Plan
              </Button>
            </Link>
          </div>
        )}

        {error && !loading && !needsPlan && (
          <div className="p-4 rounded-xl text-sm border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {!loading && !error && data && tab === "profit-and-loss" && (
          <>
            <SectionTable title="Revenue" section={data.revenue} />
            <SectionTable title="Expenses" section={data.expenses} />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <StatCard label="Net Income" value={data.net_income} accent />
            </div>
          </>
        )}

        {!loading && !error && data && tab === "balance-sheet" && (
          <>
            <SectionTable title="Assets" section={data.assets} />
            <SectionTable title="Liabilities" section={data.liabilities} />
            <SectionTable title="Equity" section={data.equity} />
            <p className="text-xs text-muted-foreground px-1">
              {data.is_balanced ? "✓ Books are balanced." : "⚠ Assets do not equal liabilities + equity for this period."}
            </p>
          </>
        )}

        {!loading && !error && data && tab === "trial-balance" && (
          <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    {["Code", "Account", "Debit", "Credit"].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(data.lines || []).length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">No ledger activity in this period.</td></tr>
                  )}
                  {(data.lines || []).map((l, i) => (
                    <tr key={i} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{l.account_code}</td>
                      <td className="px-4 py-2.5">{l.name}</td>
                      <td className="px-4 py-2.5">{money(l.debit)}</td>
                      <td className="px-4 py-2.5">{money(l.credit)}</td>
                    </tr>
                  ))}
                  {data.totals && (
                    <tr className="bg-primary/5 border-t border-primary/20 font-bold">
                      <td className="px-4 py-2.5" colSpan={2}>
                        Total {data.totals.is_balanced ? "✓ balanced" : "⚠ out of balance"}
                      </td>
                      <td className="px-4 py-2.5">{money(data.totals.debit)}</td>
                      <td className="px-4 py-2.5">{money(data.totals.credit)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!loading && !error && data && tab === "cash-flow" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Operating" value={data.operating_cash_flow} />
            <StatCard label="Investing" value={data.investing_cash_flow} />
            <StatCard label="Financing" value={data.financing_cash_flow} />
            <StatCard label="Net Change in Cash" value={data.net_change_in_cash} accent />
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Reports;
