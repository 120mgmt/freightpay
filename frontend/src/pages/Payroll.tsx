import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw, Play, Lock, Download, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface RunListItem {
  run_id: string;
  created_at?: string;
  status?: string;
  finalized?: boolean;
}

interface RunResultLine {
  contractor_id?: string;
  base_gross?: string;
  gross?: string;
  net?: string;
  accessorials?: { total?: string };
  deductions?: { total?: string };
}

interface RunDetail {
  run_id: string;
  status?: string;
  finalized?: boolean;
  results?: { results?: RunResultLine[]; totals?: Record<string, string> } | null;
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
  pending:   "bg-amber-100 text-amber-700",
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
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [needsSubscription, setNeedsSubscription] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyRun, setBusyRun] = useState<string | null>(null);
  const [openRun, setOpenRun] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [rows, setRows] = useState<PayRow[]>([]);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    setNeedsSubscription(false);
    try {
      const res = await apiFetch("/payroll/runs");
      const data = await res.json().catch(() => ({}));
      if (res.status === 402 || data.error === "subscription_inactive" || data.error === "subscription_required") {
        setNeedsSubscription(true);
      } else if (!res.ok) {
        setError(data.message || data.error || "Failed to load payroll runs.");
      } else {
        setRuns(data.runs || []);
      }
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
    (acc, r) => ({ gross: acc.gross + (Number(r.gross) || 0), net: acc.net + rowNet(r) }),
    { gross: 0, net: 0 }
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (included.length === 0) { setError("Include at least one contractor in the run."); return; }
    if (included.some((r) => rowNet(r) < 0)) { setError("Net pay cannot be negative — check deductions."); return; }
    setSaving(true);
    try {
      const createRes = await apiFetch("/payroll/runs", {
        method: "POST",
        body: JSON.stringify({
          period: `${periodStart} to ${periodEnd}`,
          contractors: included.map((r) => ({
            contractor_id: String(r.contractor_id),
            base_gross: Number(r.gross) || 0,
            accessorials: { reimbursements: Number(r.reimbursements) || 0 },
            deductions: { deductions: Number(r.deductions) || 0 },
          })),
        }),
      });
      const created = await createRes.json().catch(() => ({}));
      if (!createRes.ok) {
        setError(created.message || created.detail || created.error || "Failed to create payroll run.");
        setSaving(false);
        return;
      }
      // Execute immediately so amounts are calculated and stored
      const execRes = await apiFetch(`/payroll/runs/${created.run_id}/execute`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!execRes.ok) {
        const d = await execRes.json().catch(() => ({}));
        setError(d.message || d.detail || d.error || "Run created but calculation failed — use Execute in the list.");
      }
      setShowForm(false);
      await load();
    } catch {
      setError("Network error — check your connection.");
    }
    setSaving(false);
  };

  const handleExecute = async (runId: string) => {
    setBusyRun(runId);
    setError("");
    try {
      const res = await apiFetch(`/payroll/runs/${runId}/execute`, { method: "POST", body: JSON.stringify({}) });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.message || d.detail || d.error || "Failed to execute run.");
      }
      await load();
    } catch {
      setError("Network error — check your connection.");
    }
    setBusyRun(null);
  };

  const handleFinalize = async (runId: string) => {
    if (!confirm("Finalize this run? It becomes locked and cannot be changed.")) return;
    setBusyRun(runId);
    setError("");
    try {
      const res = await apiFetch(`/payroll/runs/${runId}/finalize`, { method: "POST", body: JSON.stringify({}) });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.message || d.detail || d.error || "Failed to finalize run.");
      }
      await load();
    } catch {
      setError("Network error — check your connection.");
    }
    setBusyRun(null);
  };

  const handleExport = async (runId: string) => {
    try {
      const res = await apiFetch(`/payroll/runs/${runId}/export`);
      if (!res.ok) { setError("Export not available for this run yet — execute it first."); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `payroll_${runId.slice(0, 8)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Network error — check your connection.");
    }
  };

  const toggleDetail = async (runId: string) => {
    if (openRun === runId) { setOpenRun(null); setDetail(null); return; }
    setOpenRun(runId);
    setDetail(null);
    try {
      const res = await apiFetch(`/payroll/runs/${runId}`);
      if (res.ok) setDetail(await res.json());
    } catch {
      /* detail is best-effort */
    }
  };

  return (
    <AppLayout active="Payroll">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Payroll Runs</h1>
            <p className="text-muted-foreground mt-1">Create, calculate, and lock contractor payroll</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw size={14} className="mr-1" /> Refresh
            </Button>
            {!needsSubscription && (
              <Button size="sm" className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]" onClick={openForm}>
                <Plus size={14} className="mr-1" /> New Run
              </Button>
            )}
          </div>
        </div>

        {needsSubscription && !loading && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-8 text-center">
            <h2 className="font-bold text-lg mb-2">Payroll requires an active plan</h2>
            <p className="text-muted-foreground mb-5 max-w-md mx-auto">
              Subscribe to the Payroll or Combo plan to run contractor payroll.
              Plans start at $29/mo with a 14-day free trial.
            </p>
            <Link to="/billing">
              <Button className="rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))] px-6">
                Choose a Plan
              </Button>
            </Link>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {/* Create run form */}
        {showForm && !needsSubscription && (
          <form onSubmit={handleCreate} className="rounded-2xl border border-border bg-card p-6 mb-8 shadow-sm">
            <h2 className="font-bold mb-4">New Payroll Run</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5 max-w-md">
              <div>
                <Label className="text-xs text-muted-foreground">Period start *</Label>
                <Input className="mt-1 bg-surface" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Period end *</Label>
                <Input className="mt-1 bg-surface" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} required />
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
                  Run Payroll
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

        {!loading && !error && !needsSubscription && runs.length === 0 && !showForm && (
          <div className="text-center py-20 border border-dashed border-border rounded-2xl bg-surface-muted/50">
            <p className="text-muted-foreground mb-4">No payroll runs yet. Create your first run to pay your contractors.</p>
            <Button onClick={openForm} className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
              <Plus size={14} className="mr-1" /> Create First Run
            </Button>
          </div>
        )}

        {!loading && !needsSubscription && runs.length > 0 && (
          <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    {["Run", "Created", "Status", "Locked", "Actions"].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => {
                    const s = (r.status || "pending").toLowerCase();
                    const isOpen = openRun === r.run_id;
                    return [
                      <tr key={r.run_id} className="border-b border-border/60 hover:bg-surface-muted/50 transition-colors">
                        <td className="px-4 py-3">
                          <button onClick={() => toggleDetail(r.run_id)} className="font-mono text-xs font-semibold inline-flex items-center gap-1 hover:text-primary">
                            {r.run_id.slice(0, 8)}
                            {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{fmtDate(r.created_at)}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[s] || "bg-muted text-muted-foreground"}`}>
                            {r.status || "—"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {r.finalized
                            ? <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Lock size={12} /> Finalized</span>
                            : <span className="text-xs text-muted-foreground">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1.5">
                            {s === "pending" && !r.finalized && (
                              <Button size="sm" variant="outline" disabled={busyRun === r.run_id} onClick={() => handleExecute(r.run_id)} className="h-7 text-xs text-primary border-primary/40 hover:bg-primary/10">
                                {busyRun === r.run_id ? <Loader2 size={12} className="animate-spin mr-1" /> : <Play size={12} className="mr-1" />}
                                Calculate
                              </Button>
                            )}
                            {s === "completed" && !r.finalized && (
                              <Button size="sm" variant="outline" disabled={busyRun === r.run_id} onClick={() => handleFinalize(r.run_id)} className="h-7 text-xs">
                                <Lock size={12} className="mr-1" /> Finalize
                              </Button>
                            )}
                            {s === "completed" && (
                              <Button size="sm" variant="outline" onClick={() => handleExport(r.run_id)} className="h-7 text-xs">
                                <Download size={12} className="mr-1" /> CSV
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>,
                      isOpen && (
                        <tr key={`${r.run_id}-detail`} className="border-b border-border/60 bg-surface-muted/40">
                          <td colSpan={5} className="px-4 py-3">
                            {!detail ? (
                              <span className="text-xs text-muted-foreground inline-flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Loading details…</span>
                            ) : detail.results?.results?.length ? (
                              <div className="text-xs">
                                <table className="w-full max-w-2xl">
                                  <thead>
                                    <tr className="text-muted-foreground uppercase tracking-wider">
                                      <th className="text-left py-1 pr-4">Contractor</th>
                                      <th className="text-right py-1 pr-4">Gross</th>
                                      <th className="text-right py-1 pr-4">Reimb.</th>
                                      <th className="text-right py-1 pr-4">Deductions</th>
                                      <th className="text-right py-1">Net</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {detail.results.results.map((l, i) => (
                                      <tr key={i}>
                                        <td className="py-1 pr-4 font-medium">#{l.contractor_id}</td>
                                        <td className="py-1 pr-4 text-right">{money(l.gross ?? l.base_gross)}</td>
                                        <td className="py-1 pr-4 text-right">{money(l.accessorials?.total)}</td>
                                        <td className="py-1 pr-4 text-right">{money(l.deductions?.total)}</td>
                                        <td className="py-1 text-right font-semibold">{money(l.net)}</td>
                                      </tr>
                                    ))}
                                    {detail.results.totals && (
                                      <tr className="border-t border-border font-bold">
                                        <td className="py-1 pr-4">Totals</td>
                                        <td className="py-1 pr-4 text-right">{money(detail.results.totals.gross)}</td>
                                        <td className="py-1 pr-4 text-right">{money(detail.results.totals.accessorials)}</td>
                                        <td className="py-1 pr-4 text-right">{money(detail.results.totals.deductions)}</td>
                                        <td className="py-1 text-right text-primary">{money(detail.results.totals.net)}</td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">No calculation results yet — click Calculate.</span>
                            )}
                          </td>
                        </tr>
                      ),
                    ];
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
