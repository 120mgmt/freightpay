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

interface W9Status {
  has_upload?: boolean;
  has_form?: boolean;
  file?: { name?: string; size?: number; uploaded_at?: string } | null;
  form?: { signature_name?: string; signed_at?: string; tin_last4?: string } | null;
}

const EMPTY_W9 = {
  name: "",
  business_name: "",
  tax_classification: "individual",
  exempt_payee_code: "",
  fatca_code: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  requester: "",
  account_numbers: "",
  tin_type: "ssn",
  tin: "",
  signature_name: "",
  certified: false,
};

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

  /* W-9 */
  const [w9For, setW9For] = useState<Contractor | null>(null);
  const [w9Status, setW9Status] = useState<W9Status | null>(null);
  const [w9Mode, setW9Mode] = useState<"choose" | "form">("choose");
  const [w9Form, setW9Form] = useState({ ...EMPTY_W9 });
  const [w9Busy, setW9Busy] = useState(false);
  const [w9Msg, setW9Msg] = useState("");

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

  const openW9 = async (c: Contractor) => {
    setW9For(c);
    setW9Mode("choose");
    setW9Msg("");
    setW9Status(null);
    // Prefill the form from what we already know about the contractor.
    setW9Form({
      ...EMPTY_W9,
      name: c.legal_name || "",
      business_name: c.business_name || "",
      tax_classification: c.tax?.classification || "individual",
      address_line1: (c.address as { line1?: string })?.line1 || "",
      city: c.address?.city || "",
      state: c.address?.state || "",
      postal_code: (c.address as { postal_code?: string })?.postal_code || "",
    });
    try {
      const res = await apiFetch(`/api/contractors/${c.id}/w9`);
      if (res.ok) setW9Status(await res.json());
    } catch {
      /* status is optional context — the actions still work without it */
    }
  };

  const uploadW9 = async (file: File) => {
    if (!w9For) return;
    setW9Busy(true);
    setW9Msg("");
    try {
      const body = new FormData();
      body.append("file", file);
      // Let the browser set the multipart boundary — do not force Content-Type.
      const res = await apiFetch(`/api/contractors/${w9For.id}/w9/upload`, { method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setW9Msg(data.message || data.error || "Could not upload the W-9.");
      } else {
        setW9Status(data);
        setW9Msg("W-9 uploaded.");
        load();
      }
    } catch {
      setW9Msg("Network error.");
    }
    setW9Busy(false);
  };

  const submitW9Form = async () => {
    if (!w9For) return;
    setW9Busy(true);
    setW9Msg("");
    try {
      const res = await apiFetch(`/api/contractors/${w9For.id}/w9/form`, {
        method: "POST",
        body: JSON.stringify(w9Form),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setW9Msg(data.message || data.error || "Could not save the W-9.");
      } else {
        setW9Status(data);
        setW9Msg("W-9 completed and signed.");
        setW9Mode("choose");
        load();
      }
    } catch {
      setW9Msg("Network error.");
    }
    setW9Busy(false);
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
                        <button
                          onClick={() => openW9(c)}
                          title="Manage W-9"
                          className={`px-2 py-0.5 rounded text-xs font-medium transition-colors hover:ring-1 hover:ring-primary/40 ${c.tax?.w9_received ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}
                        >
                          {c.tax?.w9_received ? "Received" : "Add W-9"}
                        </button>
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
        {/* ---------- W-9 ---------- */}
        {w9For && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8">
            <div className="w-full max-w-2xl rounded-2xl border border-border bg-card shadow-lg">
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <div>
                  <h3 className="font-semibold">Form W-9</h3>
                  <p className="text-xs text-muted-foreground">{displayName(w9For)}</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setW9For(null)}>Close</Button>
              </div>

              <div className="p-5 space-y-4">
                {w9Msg && (
                  <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">{w9Msg}</div>
                )}

                {w9Status && (w9Status.has_upload || w9Status.has_form) && (
                  <div className="rounded-lg border border-border bg-surface-muted px-3 py-2 text-sm space-y-1">
                    {w9Status.has_upload && (
                      <div className="flex items-center justify-between gap-2">
                        <span>Document on file: {w9Status.file?.name}</span>
                        <a
                          className="text-primary hover:underline text-xs"
                          href={`/api/contractors/${w9For.id}/w9/file`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Download
                        </a>
                      </div>
                    )}
                    {w9Status.has_form && (
                      <div>
                        Signed digitally by {w9Status.form?.signature_name}
                        {w9Status.form?.tin_last4 ? ` · TIN •••${w9Status.form.tin_last4}` : ""}
                      </div>
                    )}
                  </div>
                )}

                {w9Mode === "choose" && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-xl border border-border p-4">
                      <h4 className="font-medium text-sm mb-1">Upload a W-9</h4>
                      <p className="text-xs text-muted-foreground mb-3">
                        Already have a signed W-9? Attach the PDF or a photo (max 5 MB).
                      </p>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        disabled={w9Busy}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) uploadW9(f);
                          e.target.value = "";
                        }}
                        className="block w-full text-xs file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-foreground"
                      />
                    </div>

                    <div className="rounded-xl border border-border p-4">
                      <h4 className="font-medium text-sm mb-1">Fill it in here</h4>
                      <p className="text-xs text-muted-foreground mb-3">
                        Complete and sign the W-9 digitally — no printing or scanning.
                      </p>
                      <Button size="sm" variant="outline" onClick={() => setW9Mode("form")} disabled={w9Busy}>
                        Open W-9 form
                      </Button>
                    </div>
                  </div>
                )}

                {w9Mode === "form" && (
                  <div className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <Label className="text-xs">Name (as shown on your tax return) *</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.name}
                          onChange={(e) => setW9Form({ ...w9Form, name: e.target.value })} />
                      </div>
                      <div>
                        <Label className="text-xs">Business name / disregarded entity</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.business_name}
                          onChange={(e) => setW9Form({ ...w9Form, business_name: e.target.value })} />
                      </div>
                      <div>
                        <Label className="text-xs">Federal tax classification *</Label>
                        <select
                          className="mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                          value={w9Form.tax_classification}
                          onChange={(e) => setW9Form({ ...w9Form, tax_classification: e.target.value })}
                        >
                          {TAX_CLASSES.map((t) => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs">Exempt payee code</Label>
                          <Input className="mt-1 h-9 bg-surface" value={w9Form.exempt_payee_code}
                            onChange={(e) => setW9Form({ ...w9Form, exempt_payee_code: e.target.value })} />
                        </div>
                        <div>
                          <Label className="text-xs">FATCA code</Label>
                          <Input className="mt-1 h-9 bg-surface" value={w9Form.fatca_code}
                            onChange={(e) => setW9Form({ ...w9Form, fatca_code: e.target.value })} />
                        </div>
                      </div>
                      <div className="sm:col-span-2">
                        <Label className="text-xs">Address *</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.address_line1}
                          onChange={(e) => setW9Form({ ...w9Form, address_line1: e.target.value })} />
                      </div>
                      <div className="grid grid-cols-3 gap-3 sm:col-span-2">
                        <div>
                          <Label className="text-xs">City *</Label>
                          <Input className="mt-1 h-9 bg-surface" value={w9Form.city}
                            onChange={(e) => setW9Form({ ...w9Form, city: e.target.value })} />
                        </div>
                        <div>
                          <Label className="text-xs">State *</Label>
                          <Input className="mt-1 h-9 bg-surface" value={w9Form.state}
                            onChange={(e) => setW9Form({ ...w9Form, state: e.target.value })} />
                        </div>
                        <div>
                          <Label className="text-xs">ZIP *</Label>
                          <Input className="mt-1 h-9 bg-surface" value={w9Form.postal_code}
                            onChange={(e) => setW9Form({ ...w9Form, postal_code: e.target.value })} />
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Requester name and address</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.requester}
                          onChange={(e) => setW9Form({ ...w9Form, requester: e.target.value })} />
                      </div>
                      <div>
                        <Label className="text-xs">Account number(s)</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.account_numbers}
                          onChange={(e) => setW9Form({ ...w9Form, account_numbers: e.target.value })} />
                      </div>
                      <div>
                        <Label className="text-xs">Taxpayer ID type *</Label>
                        <select
                          className="mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                          value={w9Form.tin_type}
                          onChange={(e) => setW9Form({ ...w9Form, tin_type: e.target.value })}
                        >
                          <option value="ssn">SSN</option>
                          <option value="ein">EIN</option>
                        </select>
                      </div>
                      <div>
                        <Label className="text-xs">
                          {w9Form.tin_type === "ein" ? "EIN *" : "SSN *"}
                        </Label>
                        <Input
                          className="mt-1 h-9 bg-surface"
                          placeholder={w9Form.tin_type === "ein" ? "12-3456789" : "123-45-6789"}
                          value={w9Form.tin}
                          onChange={(e) => setW9Form({ ...w9Form, tin: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="rounded-xl border border-border bg-surface-muted p-4 space-y-3">
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Under penalties of perjury, I certify that the number shown is my correct
                        taxpayer identification number, that I am not subject to backup withholding,
                        that I am a U.S. person, and that any FATCA code entered is correct.
                      </p>
                      <label className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={w9Form.certified}
                          onChange={(e) => setW9Form({ ...w9Form, certified: e.target.checked })}
                        />
                        <span>I certify the statements above.</span>
                      </label>
                      <div>
                        <Label className="text-xs">Signature — type your full name *</Label>
                        <Input className="mt-1 h-9 bg-surface" value={w9Form.signature_name}
                          onChange={(e) => setW9Form({ ...w9Form, signature_name: e.target.value })} />
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button size="sm" onClick={submitW9Form} disabled={w9Busy}>
                        {w9Busy ? "Saving…" : "Sign and save W-9"}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setW9Mode("choose")} disabled={w9Busy}>
                        Back
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Contractors;
