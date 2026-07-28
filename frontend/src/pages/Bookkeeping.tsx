import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, RefreshCw, Layers, Plus, X, Trash2, ArrowDownCircle, ArrowUpCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const ACCOUNT_TYPES = ["asset", "liability", "equity", "revenue", "expense"] as const;

interface Account {
  id: number;
  account_code: string;
  name: string;
  account_type: string;
  normal_balance: string;
  is_active: boolean;
  is_system?: boolean;
  [key: string]: unknown;
}

interface Txn {
  id: number;
  type: string;
  date: string | null;
  description: string;
  amount: string;
  category?: { account_code: string; name: string } | null;
  paid_via?: { account_code: string; name: string } | null;
  vendor?: string | null;
}

const TYPE_ORDER = ["asset", "liability", "equity", "revenue", "expense"];
const TYPE_TEXT: Record<string, string> = {
  asset:     "text-blue-600",
  liability: "text-red-600",
  equity:    "text-violet-600",
  revenue:   "text-primary",
  expense:   "text-amber-600",
};

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n)
    ? "—"
    : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
};

const fmtDate = (s?: string | null) =>
  s ? new Date(`${s}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

const today = () => new Date().toISOString().slice(0, 10);

const Bookkeeping = () => {
  const [tab, setTab] = useState<"transactions" | "accounts">("transactions");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [needsPlan, setNeedsPlan] = useState(false);

  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<string>("expense");

  // transactions
  const [txns, setTxns] = useState<Txn[]>([]);
  const [txnLoading, setTxnLoading] = useState(false);
  const [showTxnForm, setShowTxnForm] = useState(false);
  const [savingTxn, setSavingTxn] = useState(false);
  const [busyTxn, setBusyTxn] = useState<number | null>(null);
  const [txn, setTxn] = useState({
    type: "expense",
    date: today(),
    amount: "",
    account_code: "",
    payment_account_code: "",
    description: "",
    vendor: "",
  });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/coa/accounts");
      const data = await res.json().catch(() => null);
      if (res.status === 402 || data?.error === "plan_feature_unavailable") {
        setNeedsPlan(true);
        setAccounts([]);
        setLoading(false);
        return;
      }
      setNeedsPlan(false);
      if (!res.ok) {
        setError(data?.error || "Failed to load chart of accounts.");
        setLoading(false);
        return;
      }
      setAccounts(Array.isArray(data) ? data : data?.accounts || []);
      loadTxns();
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  const loadTxns = async () => {
    setTxnLoading(true);
    try {
      const res = await apiFetch("/coa/transactions");
      const data = await res.json().catch(() => ({}));
      if (res.ok) setTxns(data.transactions || []);
    } catch {
      /* list is best-effort; accounts error banner covers connectivity */
    }
    setTxnLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const handleSeed = async () => {
    setSeeding(true);
    setMsg("");
    setError("");
    try {
      const res = await apiFetch("/coa/seed", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setMsg("Default trucking chart of accounts created.");
        await load();
      } else {
        setError(data.detail || data.error || "Seed failed.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setSeeding(false);
  };

  const handleAdd = async () => {
    setAdding(true);
    setMsg("");
    setError("");
    try {
      const res = await apiFetch("/coa/accounts", {
        method: "POST",
        body: JSON.stringify({
          account_code: newCode.trim(),
          name: newName.trim(),
          account_type: newType,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setMsg(`Account “${data.name}” (${data.account_code}) added.`);
        setNewCode("");
        setNewName("");
        setNewType("expense");
        setShowAdd(false);
        await load();
      } else {
        const map: Record<string, string> = {
          account_code_required: "Enter an account code.",
          name_required: "Enter an account name.",
          invalid_account_type: "Choose a valid account type.",
          account_code_exists: `Account code ${newCode.trim()} already exists.`,
        };
        setError(map[data.error] || data.detail || data.error || "Could not add account.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setAdding(false);
  };

  const categoryAccounts = accounts.filter(
    (a) => a.is_active && a.account_type === (txn.type === "expense" ? "expense" : "revenue")
  );
  const assetAccounts = accounts.filter((a) => a.is_active && a.account_type === "asset");

  const openTxnForm = (type: "expense" | "income") => {
    setShowTxnForm(true);
    setMsg("");
    setError("");
    setTxn({
      type,
      date: today(),
      amount: "",
      account_code: "",
      payment_account_code: assetAccounts[0]?.account_code || "",
      description: "",
      vendor: "",
    });
  };

  const handleSaveTxn = async () => {
    setSavingTxn(true);
    setMsg("");
    setError("");
    try {
      const res = await apiFetch("/coa/transactions", {
        method: "POST",
        body: JSON.stringify({
          type: txn.type,
          date: txn.date,
          amount: Number(txn.amount),
          account_code: txn.account_code,
          payment_account_code: txn.payment_account_code,
          description: txn.description.trim(),
          vendor: txn.vendor.trim() || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setMsg(`${txn.type === "expense" ? "Expense" : "Income"} of ${money(data.amount)} recorded.`);
        setShowTxnForm(false);
        await loadTxns();
      } else {
        const map: Record<string, string> = {
          invalid_amount: "Enter an amount greater than zero.",
          invalid_date: "Pick a valid date.",
          description_required: "Add a short description.",
          account_code_required: "Pick a category account.",
          payment_account_code_required: "Pick the account the money moved through.",
        };
        setError(map[data.error] || data.detail || data.error || "Could not record the transaction.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setSavingTxn(false);
  };

  const handleDeleteTxn = async (t: Txn) => {
    if (!confirm(`Delete this ${t.type} (${money(t.amount)} — ${t.description})?`)) return;
    setBusyTxn(t.id);
    try {
      const res = await apiFetch(`/coa/transactions/${t.id}`, { method: "DELETE" });
      if (res.ok) await loadTxns();
      else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || d.error || "Could not delete.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setBusyTxn(null);
  };

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    items: accounts.filter((a) => a.account_type === type),
  })).filter((g) => g.items.length > 0);

  const canTransact = accounts.length > 0;

  return (
    <AppLayout active="Bookkeeping">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Bookkeeping</h1>
            <p className="text-muted-foreground mt-1">Record money in and out, and manage your accounts</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
            {!needsPlan && !loading && tab === "accounts" && accounts.length === 0 && (
              <Button size="sm" onClick={handleSeed} disabled={seeding}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                Seed Default Accounts
              </Button>
            )}
            {!needsPlan && !loading && tab === "accounts" && (
              <Button size="sm" onClick={() => { setShowAdd((v) => !v); setError(""); setMsg(""); }}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {showAdd ? <X size={14} className="mr-1" /> : <Plus size={14} className="mr-1" />}
                {showAdd ? "Cancel" : "Add Account"}
              </Button>
            )}
            {!needsPlan && !loading && tab === "transactions" && canTransact && (
              <>
                <Button size="sm" variant="outline" onClick={() => openTxnForm("income")}
                  className="text-primary border-primary/40 hover:bg-primary/10">
                  <ArrowDownCircle size={14} className="mr-1" /> Add Income
                </Button>
                <Button size="sm" onClick={() => openTxnForm("expense")}
                  className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  <ArrowUpCircle size={14} className="mr-1" /> Add Expense
                </Button>
              </>
            )}
          </div>
        </div>

        {!needsPlan && (
          <div className="flex gap-1 border-b border-border mb-6">
            {([["transactions", "Transactions"], ["accounts", "Chart of Accounts"]] as const).map(([key, label]) => (
              <button key={key} onClick={() => { setTab(key); setError(""); setMsg(""); setShowTxnForm(false); setShowAdd(false); }}
                className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
                  tab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}>
                {label}
              </button>
            ))}
          </div>
        )}

        {needsPlan && !loading && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-8 text-center">
            <h2 className="font-bold text-lg mb-2">Bookkeeping requires an active plan</h2>
            <p className="text-muted-foreground mb-5 max-w-md mx-auto">
              Subscribe to the <b>Bookkeeping Only</b> or <b>Combo</b> plan to keep your books,
              chart of accounts, and financial reports.
            </p>
            <Link to="/billing">
              <Button className="rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))] px-6">
                Choose a Plan
              </Button>
            </Link>
          </div>
        )}

        {msg && (
          <div className="p-3 rounded-xl text-sm mb-4 border border-primary/30 bg-primary/5 text-primary">
            {msg}
          </div>
        )}
        {error && (
          <div className="p-3 rounded-xl text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading…
          </div>
        )}

        {/* ============ TRANSACTIONS TAB ============ */}
        {!loading && !needsPlan && tab === "transactions" && (
          <>
            {!canTransact ? (
              <div className="text-center py-16 border border-dashed border-border rounded-2xl bg-surface-muted/50">
                <p className="text-muted-foreground mb-4">
                  Before recording transactions, set up your accounts — one click creates a trucking-ready set.
                </p>
                <Button onClick={handleSeed} disabled={seeding}
                  className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                  Seed Default Accounts
                </Button>
              </div>
            ) : (
              <>
                {showTxnForm && (
                  <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 mb-6">
                    <h2 className="font-bold text-sm mb-3">
                      {txn.type === "expense" ? "Record an expense" : "Record income"}
                    </h2>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">Date</label>
                        <input type="date" value={txn.date} onChange={(e) => setTxn((t) => ({ ...t, date: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary" />
                      </div>
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">Amount ($)</label>
                        <input type="number" min="0.01" step="0.01" value={txn.amount} placeholder="0.00"
                          onChange={(e) => setTxn((t) => ({ ...t, amount: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary" />
                      </div>
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">
                          {txn.type === "expense" ? "Expense category" : "Income category"}
                        </label>
                        <select value={txn.account_code} onChange={(e) => setTxn((t) => ({ ...t, account_code: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary">
                          <option value="">Choose…</option>
                          {categoryAccounts.map((a) => (
                            <option key={a.id} value={a.account_code}>{a.account_code} — {a.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">
                          {txn.type === "expense" ? "Paid from" : "Deposited to"}
                        </label>
                        <select value={txn.payment_account_code} onChange={(e) => setTxn((t) => ({ ...t, payment_account_code: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary">
                          <option value="">Choose…</option>
                          {assetAccounts.map((a) => (
                            <option key={a.id} value={a.account_code}>{a.account_code} — {a.name}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">Description</label>
                        <input value={txn.description} placeholder={txn.type === "expense" ? "e.g. Fuel — I-80 truck stop" : "e.g. Load #4512 payment"}
                          onChange={(e) => setTxn((t) => ({ ...t, description: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary" />
                      </div>
                      <div>
                        <label className="text-xs font-medium block mb-1 text-muted-foreground">
                          {txn.type === "expense" ? "Vendor (optional)" : "Customer (optional)"}
                        </label>
                        <input value={txn.vendor} placeholder={txn.type === "expense" ? "e.g. Pilot" : "e.g. ABC Logistics"}
                          onChange={(e) => setTxn((t) => ({ ...t, vendor: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary" />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-4">
                      <Button size="sm" onClick={handleSaveTxn}
                        disabled={savingTxn || !txn.date || !(Number(txn.amount) > 0) || !txn.account_code || !txn.payment_account_code || !txn.description.trim()}
                        className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                        {savingTxn ? <Loader2 size={14} className="animate-spin mr-1" /> : <Plus size={14} className="mr-1" />}
                        Save {txn.type}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setShowTxnForm(false)}>Cancel</Button>
                    </div>
                  </div>
                )}

                {txnLoading ? (
                  <div className="flex items-center gap-3 text-muted-foreground py-16 justify-center">
                    <Loader2 className="animate-spin" size={18} /> Loading transactions…
                  </div>
                ) : txns.length === 0 ? (
                  <div className="text-center py-16 border border-dashed border-border rounded-2xl bg-surface-muted/50">
                    <p className="text-muted-foreground mb-4">
                      No transactions yet. Record your fuel, repairs, tolls, and income — they flow straight into your reports.
                    </p>
                    <Button onClick={() => openTxnForm("expense")}
                      className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                      <ArrowUpCircle size={14} className="mr-1" /> Record First Expense
                    </Button>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-surface-muted border-b border-border">
                            {["Date", "Description", "Category", "Account", "Amount", ""].map((h, i) => (
                              <th key={i} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {txns.map((t) => (
                            <tr key={t.id} className="border-b border-border/60 last:border-0 hover:bg-surface-muted/50 transition-colors">
                              <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">{fmtDate(t.date)}</td>
                              <td className="px-4 py-2.5">
                                <div className="font-medium">{t.description}</div>
                                {t.vendor && <div className="text-xs text-muted-foreground">{t.vendor}</div>}
                              </td>
                              <td className="px-4 py-2.5 text-muted-foreground">{t.category ? `${t.category.account_code} ${t.category.name}` : "—"}</td>
                              <td className="px-4 py-2.5 text-muted-foreground">{t.paid_via ? t.paid_via.name : "—"}</td>
                              <td className={`px-4 py-2.5 font-semibold whitespace-nowrap ${t.type === "income" ? "text-primary" : "text-foreground"}`}>
                                {t.type === "income" ? "+" : "−"}{money(t.amount)}
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                <Button size="sm" variant="outline" disabled={busyTxn === t.id}
                                  className="h-7 text-destructive border-destructive/40"
                                  onClick={() => handleDeleteTxn(t)}>
                                  {busyTxn === t.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ============ CHART OF ACCOUNTS TAB ============ */}
        {!loading && !needsPlan && tab === "accounts" && (
          <>
            {showAdd && (
              <div className="rounded-2xl border border-primary/30 bg-primary/5 p-5 mb-6">
                <h2 className="font-bold text-sm mb-3">New account</h2>
                <div className="grid sm:grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-medium block mb-1 text-muted-foreground">Account code</label>
                    <input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder="e.g. 6100"
                      className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm font-mono outline-none focus:border-primary" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1 text-muted-foreground">Name</label>
                    <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Fuel"
                      className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary" />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1 text-muted-foreground">Type</label>
                    <select value={newType} onChange={(e) => setNewType(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary capitalize">
                      {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-4">
                  <Button size="sm" onClick={handleAdd} disabled={adding || !newCode.trim() || !newName.trim()}
                    className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                    {adding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Plus size={14} className="mr-1" />}
                    Add account
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    Normal balance is set automatically (assets &amp; expenses are debit; the rest are credit).
                  </span>
                </div>
              </div>
            )}

            {accounts.length === 0 && !error && (
              <div className="text-center py-20 border border-dashed border-border rounded-2xl bg-surface-muted/50">
                <p className="text-muted-foreground mb-4">
                  No accounts yet. Seed the default trucking chart of accounts to get started.
                </p>
                <Button onClick={handleSeed} disabled={seeding}
                  className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                  Seed Default Accounts
                </Button>
              </div>
            )}

            {/* Seeding is an additive upsert, so this pulls in any categories
                added since this company was first set up. */}
            {accounts.length > 0 && (
              <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-muted/50 px-4 py-3">
                <Button size="sm" variant="outline" onClick={handleSeed} disabled={seeding}>
                  {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                  Sync default accounts
                </Button>
                <span className="text-xs text-muted-foreground">
                  Adds any new standard categories (Fuel, Tolls, Maintenance…) without touching
                  accounts you already have.
                </span>
              </div>
            )}

            {grouped.map(({ type, items }) => (
              <div key={type} className="mb-6">
                <h2 className={`text-xs font-bold uppercase tracking-widest mb-2 px-1 ${TYPE_TEXT[type] || "text-muted-foreground"}`}>
                  {type === "equity" ? "Equity" : `${type}s`} ({items.length})
                </h2>
                <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-surface-muted border-b border-border">
                          {["Code", "Name", "Normal Balance", "Status"].map((h) => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((a) => (
                          <tr key={a.id} className="border-b border-border/60 last:border-0 hover:bg-surface-muted/50 transition-colors">
                            <td className={`px-4 py-2.5 font-mono text-xs font-semibold ${TYPE_TEXT[type] || ""}`}>{a.account_code}</td>
                            <td className="px-4 py-2.5">{a.name}</td>
                            <td className="px-4 py-2.5 text-muted-foreground capitalize">{a.normal_balance}</td>
                            <td className="px-4 py-2.5">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${a.is_active ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                                {a.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default Bookkeeping;
