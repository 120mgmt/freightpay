import { useCallback, useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Download, Loader2, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type ReportType = "profit-and-loss" | "balance-sheet" | "trial-balance" | "cash-flow" | "tax-1099";

const TABS: { key: ReportType; label: string }[] = [
  { key: "profit-and-loss",  label: "Profit & Loss"  },
  { key: "balance-sheet",    label: "Balance Sheet"  },
  { key: "trial-balance",    label: "Trial Balance"  },
  { key: "cash-flow",        label: "Cash Flow"      },
  { key: "tax-1099",         label: "1099 Forms"     },
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

interface Tax1099Contractor {
  contractor_id?: number | null;
  legal_name?: string | null;
  business_name?: string | null;
  email?: string | null;
  city?: string | null;
  state?: string | null;
  tin_last4?: string | null;
  w9_received?: boolean;
  nec_total: string;
  reimbursements_total?: string;
  threshold_met?: boolean;
}
interface Tax1099Summary {
  year: number;
  contractor_count: number;
  nec_total_all: string;
  contractors: Tax1099Contractor[];
}

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const thisMonth = () => new Date().toISOString().slice(0, 7);
const janThisYear = () => `${new Date().getFullYear()}-01`;
const currentYear = () => new Date().getFullYear();

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
  const [taxYear, setTaxYear] = useState(currentYear());
  const [taxData, setTaxData] = useState<Tax1099Summary | null>(null);
  const [exporting, setExporting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [needsPlan, setNeedsPlan] = useState(false);

  const load = useCallback(async (type: ReportType) => {
    setLoading(true);
    setError("");
    setData(null);
    setTaxData(null);
    try {
      // 1099s are keyed by calendar year, not the P&L-style period range the
      // other reports share, so this tab hits a different endpoint.
      const path = type === "tax-1099" ? `/tax/1099/summary?year=${taxYear}` : `/reporting/${type}`;
      const qs = type === "tax-1099" ? "" : `?${new URLSearchParams({ period_from: from, period_to: to })}`;
      const res = await apiFetch(`${path}${qs}`);
      const json = await res.json().catch(() => ({}));
      if (res.status === 402 || json?.error === "plan_feature_unavailable") {
        setNeedsPlan(true);
      } else if (!res.ok) {
        setNeedsPlan(false);
        setError(json.message || json.error || `Failed to load ${type} report.`);
      } else {
        setNeedsPlan(false);
        if (type === "tax-1099") setTaxData(json);
        else setData(json);
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  }, [from, to, taxYear]);

  useEffect(() => { load(tab); }, [tab, load]);

  const handleExport1099 = async () => {
    setExporting(true);
    setError("");
    try {
      const res = await apiFetch(`/tax/1099/export.csv?year=${taxYear}`);
      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        setError(json.message || json.error || "Could not export 1099s.");
        setExporting(false);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `1099-nec_${taxYear}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Network error — check your connection.");
    }
    setExporting(false);
  };

  return (
    <AppLayout active="Reports">
      <div className="max-w-5xl">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Financial Reports</h1>
            <p className="text-muted-foreground mt-1">Straight from your ledger — always current</p>
          </div>
          <div className="flex items-end gap-2">
            {tab === "tax-1099" ? (
              <div>
                <Label className="text-xs text-muted-foreground">Tax year</Label>
                <Input type="number" step="1" className="mt-1 h-9 bg-surface w-24" value={taxYear}
                  onChange={(e) => setTaxYear(Number(e.target.value) || currentYear())} />
              </div>
            ) : (
              <>
                <div>
                  <Label className="text-xs text-muted-foreground">From</Label>
                  <Input type="month" className="mt-1 h-9 bg-surface" value={from} onChange={(e) => setFrom(e.target.value)} />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">To</Label>
                  <Input type="month" className="mt-1 h-9 bg-surface" value={to} onChange={(e) => setTo(e.target.value)} />
                </div>
              </>
            )}
            <Button variant="outline" size="sm" className="h-9" onClick={() => load(tab)}>
              <RefreshCw size={14} className="mr-1" /> Run
            </Button>
            {tab === "tax-1099" && (
              <Button size="sm" className="h-9" onClick={handleExport1099} disabled={exporting || !taxData}>
                {exporting ? <Loader2 size={14} className="animate-spin mr-1" /> : <Download size={14} className="mr-1" />}
                Export CSV
              </Button>
            )}
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

        {!loading && !error && taxData && tab === "tax-1099" && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              <StatCard label={`${taxData.year} contractors paid`} value={taxData.contractor_count} />
              <StatCard label="Total NEC (all contractors)" value={taxData.nec_total_all} accent />
            </div>
            <p className="text-xs text-muted-foreground px-1 mb-3">
              A contractor is 1099-NEC eligible once paid $600 or more in the year — flagged below.
            </p>
            <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-muted border-b border-border">
                      {["Contractor", "Location", "W-9", "NEC Total", "Files 1099"].map((h) => (
                        <th key={h} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {taxData.contractors.length === 0 && (
                      <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                        No contractor payments recorded for {taxData.year}.
                      </td></tr>
                    )}
                    {taxData.contractors.map((c, i) => (
                      <tr key={c.contractor_id ?? i} className="border-b border-border/60 last:border-0">
                        <td className="px-4 py-2.5 font-medium">
                          {c.legal_name || "—"}
                          {c.business_name && <div className="text-xs text-muted-foreground">{c.business_name}</div>}
                        </td>
                        <td className="px-4 py-2.5 text-muted-foreground">
                          {[c.city, c.state].filter(Boolean).join(", ") || "—"}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.w9_received ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive"}`}>
                            {c.w9_received ? "On file" : "Missing"}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-semibold">{money(c.nec_total)}</td>
                        <td className="px-4 py-2.5">
                          {c.threshold_met ? (
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary">Yes — $600+</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">Under $600</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default Reports;
