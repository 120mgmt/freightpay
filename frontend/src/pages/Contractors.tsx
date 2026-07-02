import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Contractor {
  id: number;
  legal_name?: string;
  business_name?: string;
  display_name?: string;
  effective_name?: string;
  email?: string;
  phone?: string;
  is_active?: boolean;
  tax?: { classification?: string; w9_received?: boolean };
  address?: { city?: string; state?: string };
  [key: string]: unknown;
}

const TAX_CLASSES = [
  { value: "individual",  label: "Individual" },
  { value: "sole_prop",   label: "Sole Proprietor" },
  { value: "llc",         label: "LLC" },
  { value: "partnership", label: "Partnership" },
  { value: "s_corp",      label: "S-Corp" },
  { value: "c_corp",      label: "C-Corp" },
  { value: "other",       label: "Other" },
];

const EMPTY_FORM = {
  legal_name: "",
  business_name: "",
  email: "",
  phone: "",
  address_line1: "",
  city: "",
  state: "",
  postal_code: "",
  tax_classification: "individual",
};

const displayName = (c: Contractor) =>
  c.effective_name || c.display_name || c.business_name || c.legal_name || `Contractor #${c.id}`;

const Contractors = () => {
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/contractors");
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.error || "Failed to load contractors.");
        setLoading(false);
        return;
      }
      const data = await res.json();
      setContractors(data.contractors || []);
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch("/api/contractors", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setShowForm(false);
        setForm({ ...EMPTY_FORM });
        await load();
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.error || "Failed to create contractor.");
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this contractor? Existing payroll history is kept.")) return;
    await apiFetch(`/api/contractors/${id}`, { method: "DELETE" });
    await load();
  };

  const inputCls = "mt-1 bg-surface";

  return (
    <AppLayout active="Settlements">
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Contractors</h1>
            <p className="text-muted-foreground mt-1">The drivers and contractors you settle and pay</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load}><RefreshCw size={14} className="mr-1" /> Refresh</Button>
            <Button size="sm" className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]" onClick={() => setShowForm(true)}>
              <Plus size={14} className="mr-1" /> Add Contractor
            </Button>
          </div>
        </div>

        {/* Add form */}
        {showForm && (
          <div className="rounded-2xl border border-border bg-card p-6 mb-6 shadow-sm">
            <h2 className="font-bold mb-4">New Contractor</h2>
            <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">Legal name *</Label>
                <Input className={inputCls} value={form.legal_name} onChange={(e) => set("legal_name", e.target.value)} placeholder="John Smith" required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Business name (optional)</Label>
                <Input className={inputCls} value={form.business_name} onChange={(e) => set("business_name", e.target.value)} placeholder="Smith Trucking LLC" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Email</Label>
                <Input className={inputCls} type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="john@smithtrucking.com" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Phone</Label>
                <Input className={inputCls} value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="(555) 123-4567" />
              </div>
              <div className="sm:col-span-2">
                <Label className="text-xs text-muted-foreground">Street address *</Label>
                <Input className={inputCls} value={form.address_line1} onChange={(e) => set("address_line1", e.target.value)} placeholder="123 Main St" required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">City *</Label>
                <Input className={inputCls} value={form.city} onChange={(e) => set("city", e.target.value)} placeholder="Dallas" required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-muted-foreground">State *</Label>
                  <Input className={inputCls} value={form.state} onChange={(e) => set("state", e.target.value)} placeholder="TX" required />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">ZIP *</Label>
                  <Input className={inputCls} value={form.postal_code} onChange={(e) => set("postal_code", e.target.value)} placeholder="75201" required />
                </div>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Tax classification *</Label>
                <select
                  className="mt-1 w-full h-10 rounded-md border border-input bg-surface px-3 text-sm"
                  value={form.tax_classification}
                  onChange={(e) => set("tax_classification", e.target.value)}
                >
                  {TAX_CLASSES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2 flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                <Button type="submit" disabled={saving} className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                  Save Contractor
                </Button>
              </div>
            </form>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading contractors…
          </div>
        )}

        {!loading && contractors.length === 0 && !error && (
          <div className="text-center py-20 border border-dashed border-border rounded-2xl bg-surface-muted/50">
            <p className="text-muted-foreground mb-4">No contractors yet. Add your first driver to start running settlements.</p>
            <Button onClick={() => setShowForm(true)} className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
              <Plus size={14} className="mr-1" /> Add First Contractor
            </Button>
          </div>
        )}

        {!loading && contractors.length > 0 && (
          <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    {["Name", "Email", "Phone", "Location", "Tax Class", "W-9", "Status", ""].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {contractors.map((c) => (
                    <tr key={c.id} className="border-b border-border/60 last:border-0 hover:bg-surface-muted/50 transition-colors">
                      <td className="px-4 py-3 font-semibold">{displayName(c)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.email || "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.phone || "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {[c.address?.city, c.address?.state].filter(Boolean).join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground capitalize">{(c.tax?.classification || "—").replace(/_/g, " ")}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.tax?.w9_received ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                          {c.tax?.w9_received ? "Received" : "Pending"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${c.is_active ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                          {c.is_active ? "active" : "inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button onClick={() => handleDelete(c.id)} className="text-muted-foreground hover:text-destructive transition-colors" title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Contractors;
