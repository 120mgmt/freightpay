import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, RefreshCw, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

type ReportType = "profit-and-loss" | "balance-sheet" | "trial-balance" | "cash-flow";

const TABS: { key: ReportType; label: string }[] = [
  { key: "profit-and-loss",  label: "Profit & Loss"  },
  { key: "balance-sheet",    label: "Balance Sheet"  },
  { key: "trial-balance",    label: "Trial Balance"  },
  { key: "cash-flow",        label: "Cash Flow"      },
];

interface ReportLine {
  account_code?: string;
  account_name?: string;
  name?: string;
  label?: string;
  amount?: number | string;
  balance?: number | string;
  debit?: number | string;
  credit?: number | string;
  [key: string]: unknown;
}

interface ReportSection {
  title?: string;
  name?: string;
  lines?: ReportLine[];
  items?: ReportLine[];
  total?: number | string;
  [key: string]: unknown;
}

interface ReportData {
  sections?: ReportSection[];
  lines?: ReportLine[];
  period_start?: string;
  period_end?: string;
  as_of?: string;
  net_income?: number | string;
  total_assets?: number | string;
  total_liabilities?: number | string;
  total_equity?: number | string;
  [key: string]: unknown;
}

const fmt = (v: unknown) => {
  const n = Number(v);
  if (isNaN(n)) return v ? String(v) : "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const fmtDate = (s?: string) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";

const Reports = () => {
  const [tab, setTab] = useState<ReportType>("profit-and-loss");
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async (type: ReportType) => {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const res = await apiFetch(`/reporting/${type}`);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.error || `Failed to load ${type} report.`);
        setLoading(false);
        return;
      }
      const json = await res.json();
      setData(json.data || json.report || json);
    } catch {
      setError("Network error.");
    }
    setLoading(false);
  };

  useEffect(() => { load(tab); }, [tab]);

  const sections: ReportSection[] = data?.sections || (data?.lines ? [{ lines: data.lines }] : []);

  return (
    <AppLayout active="Reports">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-white">Financial Reports</h1>
            <p className="text-muted-foreground mt-1">Review your company's financial position</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => load(tab)}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 p-1 rounded-lg border border-border" style={{ background: "rgba(14,20,27,0.5)" }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="flex-1 text-sm font-medium py-2 px-3 rounded-md transition-colors"
              style={
                tab === t.key
                  ? { background: "rgba(54,211,148,0.15)", color: "rgb(54,211,148)", border: "1px solid rgba(54,211,148,0.3)" }
                  : { color: "rgb(156,163,175)" }
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Period info */}
        {data && (data.period_start || data.as_of) && (
          <p className="text-xs text-muted-foreground mb-4">
            {data.as_of
              ? `As of ${fmtDate(data.as_of)}`
              : `${fmtDate(data.period_start)} – ${fmtDate(data.period_end)}`}
          </p>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading report…
          </div>
        )}

        {error && !loading && (
          <div className="p-4 rounded-xl text-sm" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {!loading && !error && sections.length === 0 && data && (
          <div className="text-center py-20 border border-dashed border-border rounded-xl">
            <p className="text-muted-foreground">No data available for this report period.</p>
          </div>
        )}

        {!loading && !error && sections.map((section, si) => {
          const lines: ReportLine[] = section.lines || section.items || [];
          const title = section.title || section.name || "";
          return (
            <div key={si} className="mb-6">
              {title && (
                <h2 className="text-xs font-semibold uppercase tracking-widest mb-2 px-1 text-muted-foreground">
                  {title}
                </h2>
              )}
              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-sm">
                  {tab === "trial-balance" && si === 0 && (
                    <thead>
                      <tr style={{ background: "rgba(19,27,37,0.8)", borderBottom: "1px solid var(--border)" }}>
                        {["Code", "Account", "Debit", "Credit"].map((h) => (
                          <th key={h} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-medium uppercase tracking-wider">{h}</th>
                        ))}
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {lines.map((line, li) => (
                      <tr key={li} style={{ background: li % 2 === 0 ? "rgba(19,27,37,0.4)" : "rgba(14,20,27,0.4)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                        {tab === "trial-balance" ? (
                          <>
                            <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{line.account_code || "—"}</td>
                            <td className="px-4 py-2.5 text-white">{line.account_name || line.name || "—"}</td>
                            <td className="px-4 py-2.5 text-white">{line.debit != null ? fmt(line.debit) : "—"}</td>
                            <td className="px-4 py-2.5 text-white">{line.credit != null ? fmt(line.credit) : "—"}</td>
                          </>
                        ) : (
                          <>
                            <td className="px-4 py-2.5 text-white">{line.account_name || line.name || line.label || "—"}</td>
                            <td className="px-4 py-2.5 text-right text-white">{fmt(line.amount ?? line.balance)}</td>
                          </>
                        )}
                      </tr>
                    ))}
                    {section.total != null && (
                      <tr style={{ background: "rgba(54,211,148,0.05)", borderTop: "1px solid rgba(54,211,148,0.2)" }}>
                        <td className="px-4 py-2.5 font-semibold text-white">
                          {tab === "trial-balance" ? "Total" : `Total ${title || ""}`}
                        </td>
                        {tab === "trial-balance" ? (
                          <>
                            <td className="px-4 py-2.5 font-semibold text-white">{fmt(section.total)}</td>
                            <td />
                          </>
                        ) : (
                          <td className="px-4 py-2.5 text-right font-semibold" style={{ color: "rgb(54,211,148)" }}>
                            {fmt(section.total)}
                          </td>
                        )}
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}

        {/* Summary totals */}
        {!loading && !error && data && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-2">
            {data.net_income != null && (
              <div className="rounded-xl border border-border p-4" style={{ background: "rgba(19,27,37,0.6)" }}>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Net Income</div>
                <div className="text-lg font-semibold" style={{ color: "rgb(54,211,148)" }}>{fmt(data.net_income)}</div>
              </div>
            )}
            {data.total_assets != null && (
              <div className="rounded-xl border border-border p-4" style={{ background: "rgba(19,27,37,0.6)" }}>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Assets</div>
                <div className="text-lg font-semibold text-white">{fmt(data.total_assets)}</div>
              </div>
            )}
            {data.total_liabilities != null && (
              <div className="rounded-xl border border-border p-4" style={{ background: "rgba(19,27,37,0.6)" }}>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Liabilities</div>
                <div className="text-lg font-semibold text-white">{fmt(data.total_liabilities)}</div>
              </div>
            )}
            {data.total_equity != null && (
              <div className="rounded-xl border border-border p-4" style={{ background: "rgba(19,27,37,0.6)" }}>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Equity</div>
                <div className="text-lg font-semibold text-white">{fmt(data.total_equity)}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Reports;
