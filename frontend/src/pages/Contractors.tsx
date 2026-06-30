import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Contractor {
  id: number;
  first_name?: string;
  last_name?: string;
  name?: string;
  email?: string;
  phone?: string;
  status?: string;
  pay_type?: string;
  rate?: number | string;
  created_at?: string;
  [key: string]: unknown;
}

const displayName = (c: Contractor) =>
  c.name || `${c.first_name || ""} ${c.last_name || ""}`.trim() || `Contractor #${c.id}`;

const Contractors = () => {
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone: "", pay_type: "per_mile", rate: "" });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/contractors");
      if (!res.ok) { setError("Failed to load contractors."); setLoading(false); return; }
      const data = await res.json();
      setContractors(data.contractors || data.data || []);
    } catch {
      setError("Network error.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await apiFetch("/api/contractors", {
        method: "POST",
        body: JSON.stringify({ ...form, rate: form.rate ? parseFloat(form.rate) : undefined }),
      });
      if (res.ok) {
        setShowForm(false);
        setForm({ first_name: "", last_name: "", email: "", phone: "", pay_type: "per_mile", rate: "" });
        await load();
      } else {
        const d = await res.json();
        setError(d.error || "Failed to create contractor.");
      }
    } catch {
      setError("Network error.");
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this contractor?")) return;
    await apiFetch(`/api/contractors/${id}`, { method: "DELETE" });
    await load();
  };

  return (
    <AppLayout active="Settlements">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white">Contractors</h1>
            <p className="text-muted-foreground mt-1">Manage your driver contractors</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
            <Button size="sm" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }} onClick={() => setShowForm(true)}>
              <Plus size={14} className="mr-1" /> Add Contractor
            </Button>
          </div>
        </div>

        {/* Add form */}
        {showForm && (
          <div className="rounded-xl border border-border p-6 mb-6" style={{ background: "rgba(19,27,37,0.8)" }}>
            <h2 className="text-white font-semibold mb-4">New Contractor</h2>
            <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">First Name</Label>
                <Input className="mt-1" value={form.first_name} onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Last Name</Label>
                <Input className="mt-1" value={form.last_name} onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Email</Label>
                <Input className="mt-1" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Phone</Label>
                <Input className="mt-1" value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Pay Type</Label>
                <select
                  className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 text-sm text-white"
                  value={form.pay_type}
                  onChange={e => setForm(f => ({ ...f, pay_type: e.target.value }))}
                >
                  <option value="per_mile">Per Mile</option>
                  <option value="percentage">Percentage</option>
                  <option value="flat">Flat Rate</option>
                </select>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Rate</Label>
                <Input className="mt-1" type="number" step="0.01" value={form.rate} onChange={e => setForm(f => ({ ...f, rate: e.target.value }))} placeholder="0.00" />
              </div>
              <div className="col-span-2 flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                <Button type="submit" disabled={saving} style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
                  {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  Save Contractor
                </Button>
              </div>
            </form>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl text-sm mb-4" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading contractors…
          </div>
        )}

        {!loading && contractors.length === 0 && !error && (
          <div className="text-center py-20 border border-dashed border-border rounded-xl">
            <p className="text-muted-foreground mb-4">No contractors yet.</p>
            <Button onClick={() => setShowForm(true)} style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
              <Plus size={14} className="mr-1" /> Add First Contractor
            </Button>
          </div>
        )}

        {!loading && contractors.length > 0 && (
          <div className="rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "rgba(19,27,37,0.8)", borderBottom: "1px solid var(--border)" }}>
                  {["Name", "Email", "Phone", "Pay Type", "Rate", "Status", ""].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-medium uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contractors.map((c, i) => (
                  <tr key={c.id} style={{ background: i % 2 === 0 ? "rgba(19,27,37,0.4)" : "rgba(14,20,27,0.4)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                    <td className="px-4 py-3 text-white font-medium">{displayName(c)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.email || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.phone || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground capitalize">{(c.pay_type || "—").replace(/_/g, " ")}</td>
                    <td className="px-4 py-3 text-white">{c.rate != null ? `$${Number(c.rate).toFixed(2)}` : "—"}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{ background: c.status === "active" ? "rgba(54,211,148,0.15)" : "rgba(156,163,175,0.1)", color: c.status === "active" ? "rgb(54,211,148)" : "rgb(156,163,175)" }}>
                        {c.status || "active"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => handleDelete(c.id)} className="text-muted-foreground hover:text-red-400 transition-colors" title="Delete">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Contractors;
