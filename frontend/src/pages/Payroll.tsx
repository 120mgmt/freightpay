import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PayrollRun {
  id: number;
  status: string;
  period_start?: string;
  period_end?: string;
  total_gross?: number | string;
  total_net?: number | string;
  contractor_count?: number;
  created_at?: string;
  [key: string]: unknown;
}

const STATUS_COLORS: Record<string, string> = {
  pending:    "rgba(251,191,36,0.15)",
  processing: "rgba(96,165,250,0.15)",
  completed:  "rgba(54,211,148,0.15)",
  failed:     "rgba(248,113,113,0.15)",
};
const STATUS_TEXT: Record<string, string> = {
  pending:    "rgb(251,191,36)",
  processing: "rgb(96,165,250)",
  completed:  "rgb(54,211,148)",
  failed:     "rgb(248,113,113)",
};

const fmt = (v: unknown) =>
  typeof v === "number" ? `$${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : v ? String(v) : "—";

const fmtDate = (s?: string) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

const Payroll = () => {
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/payroll/runs");
      if (!res.ok) { setError("Failed to load payroll runs."); setLoading(false); return; }
      const data = await res.json();
      setRuns(data.runs || data.payroll_runs || data.data || []);
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <AppLayout active="Payroll">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white">Payroll Runs</h1>
            <p className="text-muted-foreground mt-1">Manage contractor payroll runs</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw size={14} className="mr-1" /> Refresh
            </Button>
            <Button
              size="sm"
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
              onClick={() => alert("Create payroll run — coming soon")}
            >
              <Plus size={14} className="mr-1" /> New Run
            </Button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} />
            Loading payroll runs…
          </div>
        )}

        {error && !loading && (
          <div className="p-4 rounded-xl text-sm" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {!loading && !error && runs.length === 0 && (
          <div className="text-center py-20 border border-dashed border-border rounded-xl">
            <p className="text-muted-foreground mb-4">No payroll runs yet.</p>
            <Button
              onClick={() => alert("Create payroll run — coming soon")}
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
            >
              <Plus size={14} className="mr-1" /> Create First Run
            </Button>
          </div>
        )}

        {!loading && runs.length > 0 && (
          <div className="rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "rgba(19,27,37,0.8)", borderBottom: "1px solid var(--border)" }}>
                  {["Run #", "Status", "Period", "Contractors", "Gross", "Net", "Created"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => {
                  const s = (r.status || "pending").toLowerCase();
                  return (
                    <tr key={r.id} style={{ background: i % 2 === 0 ? "rgba(19,27,37,0.4)" : "rgba(14,20,27,0.4)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td className="px-4 py-3 text-white font-medium">#{r.id}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: STATUS_COLORS[s] || "rgba(156,163,175,0.1)", color: STATUS_TEXT[s] || "rgb(156,163,175)" }}>
                          {r.status || "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {r.period_start ? `${fmtDate(r.period_start)} – ${fmtDate(r.period_end)}` : "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{r.contractor_count ?? "—"}</td>
                      <td className="px-4 py-3 text-white">{fmt(r.total_gross)}</td>
                      <td className="px-4 py-3 text-white">{fmt(r.total_net)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{fmtDate(r.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Payroll;
