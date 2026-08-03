import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import {
  Loader2, Plus, RefreshCw, Send, Trash2, X, Check, Link2, CircleDollarSign,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface InvoiceItem {
  id?: number;
  description: string;
  quantity: string;
  unit_price: string;
  amount?: string;
}

interface Invoice {
  id: number;
  invoice_number: string;
  client_name: string;
  client_email?: string | null;
  client_address?: string | null;
  issue_date?: string | null;
  due_date?: string | null;
  status: "draft" | "sent" | "paid" | "void";
  is_overdue?: boolean;
  subtotal: string;
  tax: string;
  total: string;
  amount_paid: string;
  balance_due: string;
  notes?: string | null;
  payment_link_url?: string | null;
  items?: InvoiceItem[];
}

interface Summary {
  outstanding: string;
  paid: string;
  overdue: string;
}

const FILTERS: [string, string][] = [
  ["", "All"],
  ["draft", "Draft"],
  ["sent", "Unpaid"],
  ["overdue", "Overdue"],
  ["paid", "Paid"],
  ["void", "Void"],
];

const money = (v: unknown) => {
  const n = Number(v);
  return isNaN(n) ? "—" : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const today = () => new Date().toISOString().slice(0, 10);
const inDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

const EMPTY_ITEM: InvoiceItem = { description: "", quantity: "1", unit_price: "" };

const statusPill = (inv: Invoice) => {
  const overdue = inv.status === "sent" && inv.is_overdue;
  const label = overdue ? "Overdue" : inv.status === "sent" ? "Unpaid" : inv.status;
  const cls = overdue
    ? "bg-destructive/10 text-destructive"
    : inv.status === "paid"
    ? "bg-primary/10 text-primary"
    : inv.status === "void"
    ? "bg-muted text-muted-foreground line-through"
    : "bg-surface-muted text-muted-foreground";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${cls}`}>{label}</span>
  );
};

const Invoices = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [summary, setSummary] = useState<Summary>({ outstanding: "0", paid: "0", overdue: "0" });
  const [loading, setLoading] = useState(true);
  const [needsPlan, setNeedsPlan] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [filter, setFilter] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  /* form */
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientAddress, setClientAddress] = useState("");
  const [issueDate, setIssueDate] = useState(today());
  const [dueDate, setDueDate] = useState(inDays(30));
  const [tax, setTax] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<InvoiceItem[]>([{ ...EMPTY_ITEM }]);

  const load = async (status = filter) => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/api/invoices?status=${status}`);
      const data = await res.json().catch(() => ({}));
      if (res.status === 402 || data?.error === "plan_feature_unavailable") {
        setNeedsPlan(true);
        setInvoices([]);
      } else if (!res.ok) {
        setError(data.message || data.error || "Could not load invoices.");
      } else {
        setNeedsPlan(false);
        setInvoices(data.invoices || []);
        if (data.summary) setSummary(data.summary);
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setLoading(false);
  };

  useEffect(() => {
    load(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const subtotal = items.reduce(
    (s, i) => s + (Number(i.quantity) || 0) * (Number(i.unit_price) || 0),
    0
  );
  const grandTotal = subtotal + (Number(tax) || 0);

  const resetForm = () => {
    setEditingId(null);
    setClientName("");
    setClientEmail("");
    setClientAddress("");
    setIssueDate(today());
    setDueDate(inDays(30));
    setTax("");
    setNotes("");
    setItems([{ ...EMPTY_ITEM }]);
  };

  const openCreate = () => {
    resetForm();
    setShowForm(true);
    setMsg("");
    setError("");
  };

  const openEdit = (inv: Invoice) => {
    setEditingId(inv.id);
    setClientName(inv.client_name || "");
    setClientEmail(inv.client_email || "");
    setClientAddress(inv.client_address || "");
    setIssueDate(inv.issue_date || today());
    setDueDate(inv.due_date || "");
    setTax(Number(inv.tax) ? String(Number(inv.tax)) : "");
    setNotes(inv.notes || "");
    setItems(
      (inv.items || []).map((i) => ({
        description: i.description,
        quantity: String(Number(i.quantity)),
        unit_price: String(Number(i.unit_price)),
      }))
    );
    setShowForm(true);
    setMsg("");
    setError("");
  };

  const handleSave = async () => {
    setError("");
    if (!clientName.trim()) {
      setError("Who is this invoice for? Add a client name.");
      return;
    }
    const clean = items.filter((i) => i.description.trim());
    if (clean.length === 0) {
      setError("Add at least one line item.");
      return;
    }
    setSaving(true);
    try {
      const body = JSON.stringify({
        client_name: clientName,
        client_email: clientEmail,
        client_address: clientAddress,
        issue_date: issueDate,
        due_date: dueDate || null,
        tax: Number(tax) || 0,
        notes,
        items: clean.map((i) => ({
          description: i.description,
          quantity: Number(i.quantity) || 0,
          unit_price: Number(i.unit_price) || 0,
        })),
      });
      const res = editingId
        ? await apiFetch(`/api/invoices/${editingId}`, { method: "PATCH", body })
        : await apiFetch("/api/invoices", { method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.message || data.error || "Could not save the invoice.");
      } else {
        setMsg(editingId ? "Invoice updated." : `Invoice ${data.invoice_number} created.`);
        setShowForm(false);
        resetForm();
        load();
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setSaving(false);
  };

  const act = async (id: number, path: string, okMsg: string, body?: object) => {
    setBusyId(id);
    setError("");
    setMsg("");
    try {
      const res = await apiFetch(`/api/invoices/${id}${path}`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.message || data.error || "That didn't work.");
        if (data.payment_link_url) {
          setMsg(`Payment link ready: ${data.payment_link_url}`);
        }
      } else {
        setMsg(okMsg);
        load();
      }
    } catch {
      setError("Network error — check your connection.");
    }
    setBusyId(null);
  };

  const handleDelete = async (inv: Invoice) => {
    const isDraft = inv.status === "draft";
    if (!confirm(isDraft ? `Delete draft ${inv.invoice_number}?` : `Void ${inv.invoice_number}?`)) return;
    setBusyId(inv.id);
    try {
      const res = await apiFetch(`/api/invoices/${inv.id}`, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) setError(data.message || data.error || "Could not remove the invoice.");
      else {
        setMsg(isDraft ? "Draft deleted." : "Invoice voided.");
        load();
      }
    } catch {
      setError("Network error.");
    }
    setBusyId(null);
  };

  return (
    <AppLayout active="Invoices">
      <div className="p-6 md:p-8 max-w-7xl mx-auto">
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Invoices</h1>
            <p className="text-muted-foreground mt-1">
              Bill your clients and get paid online.
            </p>
          </div>
          {!needsPlan && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => load()}>
                <RefreshCw size={14} className="mr-1" /> Refresh
              </Button>
              <Button size="sm" onClick={openCreate}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                <Plus size={14} className="mr-1" /> New Invoice
              </Button>
            </div>
          )}
        </div>

        {needsPlan && !loading && (
          <div className="rounded-2xl border border-primary/30 bg-primary/5 p-8 text-center">
            <h2 className="font-bold text-lg mb-2">Invoicing requires an active plan</h2>
            <p className="text-muted-foreground mb-5 max-w-md mx-auto">
              Subscribe to the <b>Bookkeeping Only</b> or <b>Combo</b> plan to send invoices
              and collect payments online.
            </p>
            <Link to="/billing">
              <Button className="rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))] px-6">
                Choose a Plan
              </Button>
            </Link>
          </div>
        )}

        {msg && (
          <div className="p-3 rounded-xl text-sm mb-4 border border-primary/30 bg-primary/5 text-primary break-all">
            {msg}
          </div>
        )}
        {error && (
          <div className="p-3 rounded-xl text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {!needsPlan && (
          <div className="grid gap-4 sm:grid-cols-3 mb-6">
            {[
              ["Outstanding", summary.outstanding, "text-foreground"],
              ["Overdue", summary.overdue, "text-destructive"],
              ["Paid", summary.paid, "text-primary"],
            ].map(([label, value, cls]) => (
              <div key={label} className="rounded-2xl border border-border bg-card shadow-sm p-5">
                <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">{label}</p>
                <p className={`text-2xl font-extrabold mt-1 ${cls}`}>{money(value)}</p>
              </div>
            ))}
          </div>
        )}

        {/* ---------- form ---------- */}
        {showForm && !needsPlan && (
          <div className="rounded-2xl border border-border bg-card shadow-sm p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">{editingId ? "Edit invoice" : "New invoice"}</h2>
              <Button variant="ghost" size="sm" onClick={() => { setShowForm(false); resetForm(); }}>
                Cancel
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="lg:col-span-2">
                <Label className="text-xs">Client name *</Label>
                <Input className="mt-1 h-9 bg-surface" value={clientName}
                  onChange={(e) => setClientName(e.target.value)} placeholder="Acme Logistics" />
              </div>
              <div className="lg:col-span-2">
                <Label className="text-xs">Client email</Label>
                <Input className="mt-1 h-9 bg-surface" type="email" value={clientEmail}
                  onChange={(e) => setClientEmail(e.target.value)} placeholder="ap@acme.com" />
              </div>
              <div>
                <Label className="text-xs">Issue date</Label>
                <Input className="mt-1 h-9 bg-surface" type="date" value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)} />
              </div>
              <div>
                <Label className="text-xs">Due date</Label>
                <Input className="mt-1 h-9 bg-surface" type="date" value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)} />
              </div>
              <div className="lg:col-span-2">
                <Label className="text-xs">Client address</Label>
                <Input className="mt-1 h-9 bg-surface" value={clientAddress}
                  onChange={(e) => setClientAddress(e.target.value)} placeholder="Optional" />
              </div>
            </div>

            {/* line items */}
            <div className="mt-5">
              <Label className="text-xs">Line items</Label>
              <div className="mt-2 space-y-2">
                {items.map((it, idx) => (
                  <div key={idx} className="flex gap-2 items-end">
                    <div className="flex-1">
                      <Input className="h-9 bg-surface" placeholder="Load #4821 — Dallas to Phoenix"
                        value={it.description}
                        onChange={(e) => {
                          const next = [...items];
                          next[idx] = { ...it, description: e.target.value };
                          setItems(next);
                        }} />
                    </div>
                    <div className="w-20">
                      <Input className="h-9 bg-surface" type="number" step="0.01" min="0" placeholder="Qty"
                        value={it.quantity}
                        onChange={(e) => {
                          const next = [...items];
                          next[idx] = { ...it, quantity: e.target.value };
                          setItems(next);
                        }} />
                    </div>
                    <div className="w-28">
                      <Input className="h-9 bg-surface" type="number" step="0.01" min="0" placeholder="Rate"
                        value={it.unit_price}
                        onChange={(e) => {
                          const next = [...items];
                          next[idx] = { ...it, unit_price: e.target.value };
                          setItems(next);
                        }} />
                    </div>
                    <div className="w-28 text-right text-sm font-medium pb-2">
                      {money((Number(it.quantity) || 0) * (Number(it.unit_price) || 0))}
                    </div>
                    <button
                      onClick={() => setItems(items.length === 1 ? [{ ...EMPTY_ITEM }] : items.filter((_, i) => i !== idx))}
                      className="text-muted-foreground hover:text-destructive pb-2" title="Remove line">
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
              <Button variant="outline" size="sm" className="mt-2"
                onClick={() => setItems([...items, { ...EMPTY_ITEM }])}>
                <Plus size={14} className="mr-1" /> Add line
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 mt-5">
              <div>
                <Label className="text-xs">Notes / terms</Label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm min-h-[76px]"
                  value={notes} onChange={(e) => setNotes(e.target.value)}
                  placeholder="Payment due within 30 days. Thank you!" />
              </div>
              <div className="sm:text-right space-y-1">
                <div className="text-sm text-muted-foreground">Subtotal {money(subtotal)}</div>
                <div className="flex sm:justify-end items-center gap-2">
                  <Label className="text-xs">Tax</Label>
                  <Input className="h-8 w-28 bg-surface" type="number" step="0.01" min="0"
                    value={tax} onChange={(e) => setTax(e.target.value)} placeholder="0.00" />
                </div>
                <div className="text-lg font-extrabold">Total {money(grandTotal)}</div>
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <Button size="sm" onClick={handleSave} disabled={saving}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Check size={14} className="mr-1" />}
                {editingId ? "Save changes" : "Create invoice"}
              </Button>
            </div>
          </div>
        )}

        {/* ---------- filters ---------- */}
        {!needsPlan && (
          <div className="flex gap-1 border-b border-border mb-4 overflow-x-auto">
            {FILTERS.map(([value, label]) => (
              <button key={label} onClick={() => setFilter(value)}
                className={`px-4 py-2.5 text-sm font-semibold border-b-2 whitespace-nowrap transition-colors ${
                  filter === value ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}>
                {label}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-3 text-muted-foreground py-20 justify-center">
            <Loader2 className="animate-spin" size={20} /> Loading…
          </div>
        )}

        {!loading && !needsPlan && invoices.length === 0 && (
          <div className="text-center py-20 border border-dashed border-border rounded-2xl bg-surface-muted/50">
            <p className="text-muted-foreground mb-4">
              No invoices here yet. Create one to bill a client and collect payment online.
            </p>
            <Button onClick={openCreate}
              className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
              <Plus size={14} className="mr-1" /> New Invoice
            </Button>
          </div>
        )}

        {!loading && !needsPlan && invoices.length > 0 && (
          <div className="rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-surface-muted border-b border-border">
                    {["Invoice", "Client", "Issued", "Due", "Total", "Status", ""].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="border-b border-border/60 last:border-0 hover:bg-surface-muted/50 transition-colors">
                      <td className="px-4 py-3 font-semibold">
                        <button className="hover:text-primary" onClick={() => openEdit(inv)}>
                          {inv.invoice_number}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        {inv.client_name}
                        {inv.client_email && (
                          <div className="text-xs text-muted-foreground">{inv.client_email}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{inv.issue_date || "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{inv.due_date || "—"}</td>
                      <td className="px-4 py-3 font-semibold">{money(inv.total)}</td>
                      <td className="px-4 py-3">{statusPill(inv)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {busyId === inv.id && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
                          {inv.status !== "paid" && inv.status !== "void" && (
                            <Button variant="outline" size="sm" disabled={busyId === inv.id}
                              onClick={() => act(inv.id, "/send", `Invoice ${inv.invoice_number} emailed.`)}>
                              <Send size={13} className="mr-1" /> Send
                            </Button>
                          )}
                          {inv.payment_link_url && (
                            <a href={inv.payment_link_url} target="_blank" rel="noreferrer"
                              title="Open payment link"
                              className="p-2 text-muted-foreground hover:text-primary">
                              <Link2 size={14} />
                            </a>
                          )}
                          {inv.status === "sent" && inv.payment_link_url && (
                            <Button variant="ghost" size="sm" disabled={busyId === inv.id}
                              title="Check Stripe for payment"
                              onClick={() => act(inv.id, "/sync-payment", "Checked Stripe for payment.")}>
                              <CircleDollarSign size={13} />
                            </Button>
                          )}
                          {inv.status !== "paid" && inv.status !== "void" && (
                            <Button variant="ghost" size="sm" disabled={busyId === inv.id}
                              title="Mark as paid"
                              onClick={() => act(inv.id, "/mark-paid", `${inv.invoice_number} marked paid.`)}>
                              <Check size={14} />
                            </Button>
                          )}
                          {inv.status !== "void" && (
                            <button onClick={() => handleDelete(inv)} disabled={busyId === inv.id}
                              className="p-2 text-muted-foreground hover:text-destructive transition-colors"
                              title={inv.status === "draft" ? "Delete draft" : "Void invoice"}>
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
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

export default Invoices;
