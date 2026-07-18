import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, RefreshCw, Layers, Plus, X } from "lucide-react";
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

const TYPE_ORDER = ["asset", "liability", "equity", "revenue", "expense"];
const TYPE_TEXT: Record<string, string> = {
  asset:     "text-blue-600",
  liability: "text-red-600",
  equity:    "text-violet-600",
  revenue:   "text-primary",
  expense:   "text-amber-600",
};

const Bookkeeping = () => {
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
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

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

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    items: accounts.filter((a) => a.account_type === type),
  })).filter((g) => g.items.length > 0);

  return (
    <AppLayout active="Bookkeeping">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Chart of Accounts</h1>
            <p className="text-muted-foreground mt-1">The account structure behind your books</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
            {!needsPlan && accounts.length === 0 && !loading && (
              <Button size="sm" onClick={handleSeed} disabled={seeding}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                Seed Default Accounts
              </Button>
            )}
            {!needsPlan && !loading && (
              <Button size="sm" onClick={() => { setShowAdd((v) => !v); setError(""); setMsg(""); }}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {showAdd ? <X size={14} className="mr-1" /> : <Plus size={14} className="mr-1" />}
                {showAdd ? "Cancel" : "Add Account"}
              </Button>
            )}
          </div>
        </div>

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
            <Loader2 className="animate-spin" size={20} /> Loading accounts…
          </div>
        )}

        {!loading && accounts.length === 0 && !error && (
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

        {!loading && grouped.map(({ type, items }) => (
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
      </div>
    </AppLayout>
  );
};

export default Bookkeeping;
