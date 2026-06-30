import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, RefreshCw, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Account {
  id: number;
  account_code: string;
  name: string;
  type: string;
  normal_balance: string;
  is_active: boolean;
  [key: string]: unknown;
}

const TYPE_ORDER = ["asset", "liability", "equity", "revenue", "expense"];
const TYPE_COLOR: Record<string, string> = {
  asset:     "rgb(96,165,250)",
  liability: "rgb(248,113,113)",
  equity:    "rgb(167,139,250)",
  revenue:   "rgb(54,211,148)",
  expense:   "rgb(251,191,36)",
};

const Bookkeeping = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/coa/accounts");
      if (!res.ok) { setError("Failed to load chart of accounts."); setLoading(false); return; }
      const data = await res.json();
      setAccounts(data.accounts || data.data || []);
    } catch {
      setError("Network error.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSeed = async () => {
    setSeeding(true);
    setMsg("");
    try {
      const res = await apiFetch("/coa/seed", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setMsg("Default chart of accounts created.");
        await load();
      } else {
        setError(data.error || "Seed failed.");
      }
    } catch {
      setError("Network error.");
    }
    setSeeding(false);
  };

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    items: accounts.filter((a) => a.type === type),
  })).filter((g) => g.items.length > 0);

  return (
    <AppLayout active="Bookkeeping">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white">Chart of Accounts</h1>
            <p className="text-muted-foreground mt-1">Your company's account structure</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
            {accounts.length === 0 && (
              <Button size="sm" onClick={handleSeed} disabled={seeding}
                style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
                {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
                Seed Default Accounts
              </Button>
            )}
          </div>
        </div>

        {msg && (
          <div className="p-3 rounded-xl text-sm mb-4" style={{ background: "rgba(54,211,148,0.1)", border: "1px solid rgba(54,211,148,0.3)", color: "rgb(54,211,148)" }}>
            {msg}
          </div>
        )}
        {error && (
          <div className="p-3 rounded-xl text-sm mb-4" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading accounts…
          </div>
        )}

        {!loading && accounts.length === 0 && !error && (
          <div className="text-center py-20 border border-dashed border-border rounded-xl">
            <p className="text-muted-foreground mb-4">No accounts yet. Seed the default trucking chart of accounts to get started.</p>
            <Button onClick={handleSeed} disabled={seeding} style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
              {seeding ? <Loader2 size={14} className="animate-spin mr-1" /> : <Layers size={14} className="mr-1" />}
              Seed Default Accounts
            </Button>
          </div>
        )}

        {!loading && grouped.map(({ type, items }) => (
          <div key={type} className="mb-6">
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-2 px-1" style={{ color: TYPE_COLOR[type] || "rgb(156,163,175)" }}>
              {type}s ({items.length})
            </h2>
            <div className="rounded-xl border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: "rgba(19,27,37,0.8)", borderBottom: "1px solid var(--border)" }}>
                    {["Code", "Name", "Normal Balance", "Status"].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 text-xs text-muted-foreground font-medium uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((a, i) => (
                    <tr key={a.id} style={{ background: i % 2 === 0 ? "rgba(19,27,37,0.4)" : "rgba(14,20,27,0.4)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: TYPE_COLOR[type] || "white" }}>{a.account_code}</td>
                      <td className="px-4 py-2.5 text-white">{a.name}</td>
                      <td className="px-4 py-2.5 text-muted-foreground capitalize">{a.normal_balance}</td>
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{ background: a.is_active ? "rgba(54,211,148,0.15)" : "rgba(156,163,175,0.1)", color: a.is_active ? "rgb(54,211,148)" : "rgb(156,163,175)" }}>
                          {a.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </AppLayout>
  );
};

export default Bookkeeping;
