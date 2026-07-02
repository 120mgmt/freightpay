import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface PayrollRun {
  id: number;
  status?: string;
  period_start?: string;
  period_end?: string;
  pay_date?: string;
  gross_total?: string;
  net_total?: string;
  created_at?: string;
  payload?: { contractors?: unknown[] } | null;
  [key: string]: unknown;
}

interface ContractorOpt {
  id: number;
  effective_name?: string;
  legal_name?: string;
}

interface PayRow {
  contractor_id: number;
  name: string;
  included: boolean;
  gross: string;
  reimbursements: string;
  deductions: string;
}

const STATUS_STYLES: Record<string, string> = {
  draft:     "bg-amber-100 text-amber-700",
  submitted: "bg-blue-100 text-blue-700",
  completed: "bg-primary/10 text-primary",
  failed:    "bg-red-100 text-red-700",
};

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const fmtDate = (s?: string) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

const rowNet = (r: PayRow) =>
  (Number(r.gross) || 0) + (Number(r.reimbursements) || 0) - (Number(r.deductions) || 0);

const Payroll = () => {
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [rows, setRows] = useState<PayRow[]>([]);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [payDate, setPayDate] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/payroll/runs");
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.message || d.error || "Failed to load payroll runs.");
        setLoading(false);
        return;
      }
      const data = await res.json();
      setRuns(data.runs || []);
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openForm = async () => {
    setError("");
    try {
      const res = await apiFetch("/api/contractors");
      const d = await res.json().catch(() => ({}));
      const list: ContractorOpt[] = d.contractors || [];
      if (!res.ok || list.length === 0) {
        setError("Add at least one contractor before running payroll (Settlements page).");
        return;
      }
      setRows(
        list.map((c) => ({
          contractor_id: c.id,
          name: c.effective_name || c.legal_name || `Contractor #${c.id}`,
          included: true,
          gross: "",
          reimbursements: "",
          deductions: "",
        }))
      );
      setShowForm(true);
    } catch {
      setError("Network error — check your connection.");
    }
  };

  const setRow = (id: number, field: keyof PayRow, value: string | boolean) =>
    setRows((rs) => rs.map((r) => (r.contractor_id === id ? { ...r, [field]: value } : r)));

  const included = rows.filter((r) => r.included);
  const totals = included.reduce(
    (acc, r) => ({
      gross: acc.gross + (Number(r.gross) || 0),
      net: acc.net + rowNet(r),
    }),
    { gross: 0, net: 0 }
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (included.length === 0) { setError("Include at least one contractor in the run."); return; }
    if (included.some((r) => rowNet(r) < 0)) { setError("Net pay cannot be negative — check deductions."); return; }
    setSaving(true);
    try {
      const res = await apiFetch("/payroll/runs", {
        method: "POST",
        body: JSON.stringify({
          period_start: periodStart,
          period_end: periodEnd,
          pay_date: payDate,
          contractors: included.map((r) => ({
            contractor_id: r.contractor_id,
            gross: (Number(r.gross) || 0).toFixed(2),
            reimbursements: (Number(r.reimbursements) || 0).toFixed(2),
            deductions: (Number(r.deductions) || 0).toFixed(2),
            net: rowNet(r).toFixed(2),
          })),
        }),
      });
      if (res.ok) {
        setShowForm(false);
        await load();
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.message || d.error || "Failed to create payroll run.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setSaving(false);
  };

  const handleSubmit = async (runId: number) => {
    setSubmittingId(runId);
    setError("");
    try {
      const res = await apiFetch("/payroll/provider/submit", {
        method: "POST",
        body: JSON.stringify({ run_id: runId, provider_name: "manual", provider_payload: {} }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.message || d.error || "Failed to submit payroll run.");
      }
      await load();
    } catch {
      setError("Network error — check your connection.");
    }
    setSubmittingId(null);
  };

  return (
    <AppLayout active="Payroll">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Payroll Runs</h1>
            <p className="text-muted-foreground mt-1">Create, review, and submit contractor payroll</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw size={14} className="mr-1" /> Refresh
            </Button>
            <Button size="sm" className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]" onClick={openForm}>
              <Plus size={14} className="mr-1" /> New Run
            </Button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {/* Create run form */}
        {showForm && (
          <form onSubmit={handleCreate} className="rounded-2xl border border-border bg-card p-6 mb-8 shadow-sm">
            <h2 className="font-bold mb-4">New Payroll Run</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
              <div>
                <Label className="text-xs text-muted-foreground">Period start *</Label>
                <Input className="mt-1 bg-surface" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Period end *</Label>
                <Input className="mt-1 bg-surface" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Pay date *</Label>
                <Input className="mt-1 bg-surface" type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} required />
              </div>
            </div>

            <div className="rounded-xl border border-border overflow-hidden mb-4">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-surface-muted border-b border-border">
                      {["Pay", "Contractor", "Gross ($)", "Reimbursements ($)", "Deductions ($)", "Net"].map((h) => (
                        <th key={h} className="text-left px-3 py-2.5 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.contractor_id} className="border-b border-border/60 last:border-0">
                        <td className="px-3 py-2">
                          <input type="checkbox" checked={r.included} onChange={(e) => setRow(r.contractor_id, "included", e.target.checked)} className="accent-[hsl(var(--primary))] h-4 w-4" />
                        </td>
                        <td className="px-3 py-2 font-medium whitespace-nowrap">{r.name}</td>
                        <td className="px-3 py-2"><Input type="number" step="0.01" min="0" className="h-9 w-28 bg-surface" value={r.gross} disabled={!r.included} onChange={(e) => setRow(r.contractor_id, "gross", e.target.value)} placeholder="0.00" /></td>
                        <td className="px-3 py-2"><Input type="number" step="0.01" min="0" className="h-9 w-28 bg-surface" value={r.reimbursements} disabled={!r.included} onChange={(e) => setRow(r.contractor_id, "reimbursements", e.target.value)} placeholder="0.00" /></td>
                        <td className="px-3 py-2"><Input type="number" step="0.01" min="0" className="h-9 w-28 bg-surface" value={r.deductions} disabled={!r.included} onChange={(e) => setRow(r.contractor_id, "deductions", e.target.value)} placeholder="0.00" /></td>
                        <td className={`px-3 py-2 font-semibold whitespace-nowrap ${rowNet(r) < 0 ? "text-destructive" : ""}`}>{r.included ? money(rowNet(r)) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="text-sm text-muted-foreground">
                {included.length} contractor{included.length === 1 ? "" : "s"} ·
                Gross <span className="font-semibold text-foreground">{money(totals.gross)}</span> ·
                Net <span className="font-semibold text-primary">{money(totals.net)}</span>
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                <Button type="submit" disabled={saving} className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  Create Run
                </Button>
              </div>
            </div>
          </form>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading payroll runs…
          </div>
        )}

        {!loading && !error && runs.length === 0 && !showForm && (
          <div className="text-center py-20 border border-dashed border-border rounded-2xl bg-surface-muted/50">
            <p className="text-muted-foreground mb-4">No payroll runs yet. Create your first run to pay your contractors.</p>
            <Button onClick={openForm} className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
              <Plus size={14} className="mr-1" /> Create First Run
            </Button>
          </div>
        )}

        {!loading && runs.length > 0 && (
          <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    {["Run #", "Status", "Period", "Pay Date", "Contractors", "Gross", "Net", ""].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => {
                    const s = (r.status || "draft").toLowerCase();
                    const count = Array.isArray(r.payload?.contractors) ? r.payload!.contractors!.length : "—";
                    return (
                      <tr key={r.id} className="border-b border-border/60 last:border-0 hover:bg-surface-muted/50 transition-colors">
                        <td className="px-4 py-3 font-semibold">#{r.id}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[s] || "bg-muted text-muted-foreground"}`}>
                            {r.status || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                          {r.period_start ? `${fmtDate(r.period_start)} – ${fmtDate(r.period_end)}` : "—"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{fmtDate(r.pay_date)}</td>
                        <td className="px-4 py-3 text-muted-foreground">{count}</td>
                        <td className="px-4 py-3">{money(r.gross_total)}</td>
                        <td className="px-4 py-3 font-semibold">{money(r.net_total)}</td>
                        <td className="px-4 py-3">
                          {s === "draft" && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={submittingId === r.id}
                              onClick={() => handleSubmit(r.id)}
                              className="text-primary border-primary/40 hover:bg-primary/10"
                            >
                              {submittingId === r.id
                                ? <Loader2 size={13} className="animate-spin mr-1" />
                                : <Send size={13} className="mr-1" />}
                              Submit
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Payroll;
