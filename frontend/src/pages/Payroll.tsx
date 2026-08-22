import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw, Play, Lock, Download, ChevronDown, ChevronUp, X } from "lucide-react";
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
  accessorials?: { total?: string; items?: Record<string, string> };
  deductions?: { total?: string; items?: Record<string, string> };
  mileage?: { miles?: string; rate_per_mile?: string; total?: string } | null;
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

interface PayItem { kind: string; amount: string; }

interface PayRow {
  contractor_id: number;
  name: string;
  included: boolean;
  flatPay: string;
  miles: string;
  ratePerMile: string;
  accessorials: PayItem[];
  deductions: PayItem[];
}

const ACCESSORIAL_TYPES: [string, string][] = [
  ["tonu", "TONU (truck ordered, not used)"],
  ["detention", "Detention"],
  ["layover", "Layover"],
  ["stop_pay", "Stop pay"],
  ["tarp", "Tarp pay"],
  ["hazmat", "Hazmat"],
  ["fuel_bonus", "Fuel bonus"],
  ["bonus", "Bonus"],
  ["reimbursements", "Reimbursement"],
  ["misc", "Other pay"],
];

const DEDUCTION_TYPES: [string, string][] = [
  ["fuel_advance", "Fuel advance"],
  ["cash_advance", "Cash advance"],
  ["insurance", "Insurance"],
  ["escrow", "Escrow"],
  ["maintenance", "Maintenance"],
  ["trailer_rent", "Trailer rent"],
  ["factoring_fee", "Factoring fee"],
  ["garnishment", "Garnishment"],
  ["misc", "Other deduction"],
];

const ITEM_LABELS: Record<string, string> = Object.fromEntries([
  ...ACCESSORIAL_TYPES,
  ...DEDUCTION_TYPES,
  ["mileage_reimbursement", "Mileage pay"],
]);

const itemLabel = (key: string) => {
  const base = key.replace(/_\d+$/, "");
  return ITEM_LABELS[base] || base.replace(/_/g, " ");
};

const STATUS_STYLES: Record<string, string> = {
  pending:   "bg-amber-100 text-amber-700",
  completed: "bg-primary/10 text-primary",
  failed:    "bg-red-100 text-red-700",
};

// Normalizes numeric text input so a locale/keyboard decimal comma (or any
// stray character) can't silently zero out a value. Native <input type="number">
// rejects "0,60" as invalid and reports e.target.value as "" on some mobile
// keyboards/locales — this keeps the field a plain text input under our control.
const sanitizeDecimal = (raw: string) => {
  const normalized = raw.replace(/,/g, ".").replace(/[^0-9.]/g, "");
  const firstDot = normalized.indexOf(".");
  if (firstDot === -1) return normalized;
  return normalized.slice(0, firstDot + 1) + normalized.slice(firstDot + 1).replace(/\./g, "");
};

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const fmtDate = (s?: string) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

const itemsTotal = (items: PayItem[]) =>
  items.reduce((s, i) => s + (Number(i.amount) || 0), 0);

const mileagePay = (r: PayRow) => (Number(r.miles) || 0) * (Number(r.ratePerMile) || 0);

const rowGross = (r: PayRow) =>
  (Number(r.flatPay) || 0) + mileagePay(r) + itemsTotal(r.accessorials);

const rowNet = (r: PayRow) => rowGross(r) - itemsTotal(r.deductions);

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
          flatPay: "",
          miles: "",
          ratePerMile: "",
          accessorials: [],
          deductions: [],
        }))
      );
      setShowForm(true);
    } catch {
      setError("Network error — check your connection.");
    }
  };

  const setRow = (id: number, field: keyof PayRow, value: string | boolean) =>
    setRows((rs) => rs.map((r) => (r.contractor_id === id ? { ...r, [field]: value } : r)));

  const addItem = (id: number, list: "accessorials" | "deductions") =>
    setRows((rs) =>
      rs.map((r) =>
        r.contractor_id === id
          ? { ...r, [list]: [...r[list], { kind: list === "accessorials" ? "tonu" : "fuel_advance", amount: "" }] }
          : r
      )
    );

  const setItem = (id: number, list: "accessorials" | "deductions", idx: number, field: keyof PayItem, value: string) =>
    setRows((rs) =>
      rs.map((r) =>
        r.contractor_id === id
          ? { ...r, [list]: r[list].map((it, i) => (i === idx ? { ...it, [field]: value } : it)) }
          : r
      )
    );

  const removeItem = (id: number, list: "accessorials" | "deductions", idx: number) =>
    setRows((rs) =>
      rs.map((r) =>
        r.contractor_id === id ? { ...r, [list]: r[list].filter((_, i) => i !== idx) } : r
      )
    );

  const included = rows.filter((r) => r.included);
  const totals = included.reduce(
    (acc, r) => ({ gross: acc.gross + rowGross(r), net: acc.net + rowNet(r) }),
    { gross: 0, net: 0 }
  );

  // named items -> engine dict, deduping repeated kinds (tonu, tonu_2, ...)
  const itemsToDict = (items: PayItem[]) => {
    const d: Record<string, number> = {};
    items.forEach((it) => {
      const amt = Number(it.amount) || 0;
      if (amt <= 0) return;
      let key = it.kind;
      let n = 2;
      while (key in d) key = `${it.kind}_${n++}`;
      d[key] = amt;
    });
    return d;
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (included.length === 0) { setError("Include at least one contractor in the run."); return; }
    if (included.some((r) => rowGross(r) <= 0)) { setError("Every included contractor needs some pay — enter flat pay, miles, or a pay item (or untick them)."); return; }
    if (included.some((r) => rowNet(r) < 0)) { setError("Net pay cannot be negative — check deductions."); return; }
    setSaving(true);
    try {
      const createRes = await apiFetch("/payroll/runs", {
        method: "POST",
        body: JSON.stringify({
          period: `${periodStart} to ${periodEnd}`,
          contractors: included.map((r) => {
            const c: Record<string, unknown> = {
              contractor_id: String(r.contractor_id),
              base_gross: Number(r.flatPay) || 0,
              accessorials: itemsToDict(r.accessorials),
              deductions: itemsToDict(r.deductions),
            };
            const miles = Number(r.miles) || 0;
            const rate = Number(r.ratePerMile) || 0;
            if (miles > 0 && rate > 0) c.mileage = { miles, rate_per_mile: rate };
            return c;
          }),
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

            <div className="space-y-3 mb-4">
              {rows.map((r) => (
                <div
                  key={r.contractor_id}
                  className={`rounded-xl border p-4 ${r.included ? "border-border bg-surface/60" : "border-border/50 bg-surface-muted/30 opacity-70"}`}
                >
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <label className="flex items-center gap-2.5 font-semibold cursor-pointer">
                      <input type="checkbox" checked={r.included} onChange={(e) => setRow(r.contractor_id, "included", e.target.checked)} className="accent-[hsl(var(--primary))] h-4 w-4" />
                      {r.name}
                    </label>
                    {r.included && (
                      <div className="text-sm">
                        <span className="text-muted-foreground mr-3">Gross {money(rowGross(r))}</span>
                        <span className={`font-bold ${rowNet(r) < 0 ? "text-destructive" : "text-primary"}`}>Net {money(rowNet(r))}</span>
                      </div>
                    )}
                  </div>

                  {r.included && (
                    <div className="mt-4 space-y-4">
                      {/* Pay basis */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div>
                          <Label className="text-xs text-muted-foreground">Flat pay ($)</Label>
                          <Input type="text" inputMode="decimal" className="mt-1 h-9 bg-surface" value={r.flatPay}
                            onChange={(e) => setRow(r.contractor_id, "flatPay", sanitizeDecimal(e.target.value))} placeholder="0.00" />
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Miles</Label>
                          <Input type="text" inputMode="decimal" className="mt-1 h-9 bg-surface" value={r.miles}
                            onChange={(e) => setRow(r.contractor_id, "miles", sanitizeDecimal(e.target.value))} placeholder="0" />
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Rate per mile ($)</Label>
                          <Input type="text" inputMode="decimal" className="mt-1 h-9 bg-surface" value={r.ratePerMile}
                            onChange={(e) => setRow(r.contractor_id, "ratePerMile", sanitizeDecimal(e.target.value))} placeholder="0.60" />
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Mileage pay</Label>
                          <div className="mt-1 h-9 flex items-center px-3 rounded-md border border-border bg-surface-muted/60 text-sm font-semibold">
                            {money(mileagePay(r))}
                          </div>
                        </div>
                      </div>

                      {/* Pay items (accessorials) */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <Label className="text-xs text-muted-foreground">Extra pay items</Label>
                          <Button type="button" size="sm" variant="outline" className="h-7 text-xs"
                            onClick={() => addItem(r.contractor_id, "accessorials")}>
                            <Plus size={12} className="mr-1" /> TONU, detention…
                          </Button>
                        </div>
                        {r.accessorials.length === 0 ? (
                          <p className="text-xs text-muted-foreground/70">None — add TONU, detention, layover, stop pay, bonuses…</p>
                        ) : (
                          <div className="space-y-2">
                            {r.accessorials.map((it, idx) => (
                              <div key={idx} className="flex items-center gap-2">
                                <select value={it.kind} onChange={(e) => setItem(r.contractor_id, "accessorials", idx, "kind", e.target.value)}
                                  className="h-9 rounded-md border border-border bg-surface px-2 text-sm outline-none focus:border-primary flex-1 max-w-xs">
                                  {ACCESSORIAL_TYPES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                                </select>
                                <Input type="text" inputMode="decimal" className="h-9 w-32 bg-surface" value={it.amount}
                                  onChange={(e) => setItem(r.contractor_id, "accessorials", idx, "amount", sanitizeDecimal(e.target.value))} placeholder="0.00" />
                                <button type="button" onClick={() => removeItem(r.contractor_id, "accessorials", idx)}
                                  className="text-muted-foreground hover:text-destructive" title="Remove">
                                  <X size={15} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Deductions */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <Label className="text-xs text-muted-foreground">Deductions</Label>
                          <Button type="button" size="sm" variant="outline" className="h-7 text-xs"
                            onClick={() => addItem(r.contractor_id, "deductions")}>
                            <Plus size={12} className="mr-1" /> Advance, escrow…
                          </Button>
                        </div>
                        {r.deductions.length === 0 ? (
                          <p className="text-xs text-muted-foreground/70">None — add fuel advances, insurance, escrow…</p>
                        ) : (
                          <div className="space-y-2">
                            {r.deductions.map((it, idx) => (
                              <div key={idx} className="flex items-center gap-2">
                                <select value={it.kind} onChange={(e) => setItem(r.contractor_id, "deductions", idx, "kind", e.target.value)}
                                  className="h-9 rounded-md border border-border bg-surface px-2 text-sm outline-none focus:border-primary flex-1 max-w-xs">
                                  {DEDUCTION_TYPES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                                </select>
                                <Input type="text" inputMode="decimal" className="h-9 w-32 bg-surface" value={it.amount}
                                  onChange={(e) => setItem(r.contractor_id, "deductions", idx, "amount", sanitizeDecimal(e.target.value))} placeholder="0.00" />
                                <button type="button" onClick={() => removeItem(r.contractor_id, "deductions", idx)}
                                  className="text-muted-foreground hover:text-destructive" title="Remove">
                                  <X size={15} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
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
                                      <th className="text-right py-1 pr-4">Miles</th>
                                      <th className="text-right py-1 pr-4">Mileage</th>
                                      <th className="text-right py-1 pr-4">Extras</th>
                                      <th className="text-right py-1 pr-4">Gross</th>
                                      <th className="text-right py-1 pr-4">Deductions</th>
                                      <th className="text-right py-1">Net</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {detail.results.results.map((l, i) => {
                                      const payBits: string[] = [];
                                      if (Number(l.base_gross) > 0) payBits.push(`Flat ${money(l.base_gross)}`);
                                      if (l.mileage && Number(l.mileage.total) > 0)
                                        payBits.push(`${Number(l.mileage.miles).toLocaleString()} mi × ${money(l.mileage.rate_per_mile)} = ${money(l.mileage.total)}`);
                                      Object.entries(l.accessorials?.items || {}).forEach(([k, v]) => {
                                        if (k !== "mileage_reimbursement" && Number(v) > 0) payBits.push(`${itemLabel(k)} ${money(v)}`);
                                      });
                                      const dedBits = Object.entries(l.deductions?.items || {})
                                        .filter(([, v]) => Number(v) > 0)
                                        .map(([k, v]) => `${itemLabel(k)} ${money(v)}`);
                                      // "Extras" excludes mileage so the row reconciles:
                                      // Gross = Flat + Mileage + Extras.
                                      const mileagePayAmt = Number(l.mileage?.total || 0);
                                      const otherExtras = Number(l.accessorials?.total || 0) - mileagePayAmt;
                                      return [
                                        <tr key={i}>
                                          <td className="py-1 pr-4 font-medium">#{l.contractor_id}</td>
                                          <td className="py-1 pr-4 text-right">
                                            {mileagePayAmt > 0 ? Number(l.mileage?.miles || 0).toLocaleString() : "—"}
                                          </td>
                                          <td className="py-1 pr-4 text-right">{mileagePayAmt > 0 ? money(mileagePayAmt) : "—"}</td>
                                          <td className="py-1 pr-4 text-right">{money(otherExtras)}</td>
                                          <td className="py-1 pr-4 text-right">{money(l.gross ?? l.base_gross)}</td>
                                          <td className="py-1 pr-4 text-right">{money(l.deductions?.total)}</td>
                                          <td className="py-1 text-right font-semibold">{money(l.net)}</td>
                                        </tr>,
                                        (payBits.length > 0 || dedBits.length > 0) && (
                                          <tr key={`${i}-items`}>
                                            <td colSpan={7} className="pb-2 pt-0 text-muted-foreground">
                                              {payBits.length > 0 && <span>Pay: {payBits.join(" · ")}</span>}
                                              {payBits.length > 0 && dedBits.length > 0 && <span> &nbsp;|&nbsp; </span>}
                                              {dedBits.length > 0 && <span>Deductions: {dedBits.join(" · ")}</span>}
                                            </td>
                                          </tr>
                                        ),
                                      ];
                                    })}
                                    {detail.results.totals && (
                                      <tr className="border-t border-border font-bold">
                                        <td className="py-1 pr-4">Totals</td>
                                        <td className="py-1 pr-4 text-right">
                                          {Number(detail.results.totals.miles || 0).toLocaleString()}
                                        </td>
                                        <td className="py-1 pr-4 text-right">{money(detail.results.totals.mileage)}</td>
                                        <td className="py-1 pr-4 text-right">
                                          {money(
                                            Number(detail.results.totals.accessorials || 0) -
                                              Number(detail.results.totals.mileage || 0)
                                          )}
                                        </td>
                                        <td className="py-1 pr-4 text-right">{money(detail.results.totals.gross)}</td>
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
