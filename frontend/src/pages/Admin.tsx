import { useCallback, useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Loader2, Building2, Users as UsersIcon, ShieldAlert, RefreshCw,
  Search, CheckCircle2, XCircle, KeyRound, ChevronLeft, ChevronRight,
  ShieldCheck, ShieldOff, Trash2,
} from "lucide-react";

/* ---------- types ---------- */

interface Overview {
  companies: { total: number; active: number; with_stripe_customer: number };
  users: { total: number; active: number; verified: number; new_last_7d: number; new_last_30d: number };
  payroll_runs: { total: number; finalized: number };
  recent_signups: AdminUser[];
}

interface AdminUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  company_id: number;
  company_name?: string | null;
  created_at?: string | null;
  is_platform_admin?: boolean;
}

interface AdminCompany {
  id: number;
  name: string;
  slug: string;
  stripe_customer_id?: string | null;
  plan_override?: string | null;
  is_active: boolean;
  created_at?: string | null;
  user_count?: number;
}

interface CompanyDetail {
  company: AdminCompany;
  users: AdminUser[];
  payroll_runs: { run_id: string; created_at: number | null; status: string; finalized: boolean }[];
  subscription: { status: string; plan?: string | null; current_period_end?: string | null; detail?: string };
}

interface AdminRun {
  run_id: string;
  company_id: number;
  company_name?: string | null;
  created_at: number | null;
  status: string;
  finalized: boolean;
  total_net?: number | null;
}

interface AdminSub {
  company_id: number;
  company_name: string;
  status: string;
  plan?: string | null;
  current_period_end?: string | null;
  detail?: string;
}

/* ---------- helpers ---------- */

const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

const fmtEpoch = (ts?: number | null) => {
  if (!ts) return "—";
  const ms = ts > 1e12 ? ts : ts * 1000;
  return new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

const PLAN_LABEL: Record<string, string> = {
  combo: "Combo",
  payroll_only: "Payroll Only",
  bookkeeping_only: "Bookkeeping Only",
};

const statusPill = (ok: boolean, yes: string, no: string) => (
  <span
    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
      ok ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive"
    }`}
  >
    {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
    {ok ? yes : no}
  </span>
);

const TABS = ["Overview", "Companies", "Users", "Payroll", "Subscriptions"] as const;
type Tab = (typeof TABS)[number];

/* ---------- page ---------- */

const Admin = () => {
  const [tab, setTab] = useState<Tab>("Overview");
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState("");

  /* overview */
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loadingOverview, setLoadingOverview] = useState(false);

  /* companies */
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [companyTotal, setCompanyTotal] = useState(0);
  const [companyPage, setCompanyPage] = useState(1);
  const [companyQuery, setCompanyQuery] = useState("");
  const [loadingCompanies, setLoadingCompanies] = useState(false);
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<number | null>(null);

  /* users */
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userPage, setUserPage] = useState(1);
  const [userQuery, setUserQuery] = useState("");
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [busyUser, setBusyUser] = useState<number | null>(null);
  const [resetLink, setResetLink] = useState<{ userId: number; url: string } | null>(null);

  /* payroll */
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [runTotal, setRunTotal] = useState(0);
  const [runPage, setRunPage] = useState(1);
  const [loadingRuns, setLoadingRuns] = useState(false);

  /* subscriptions */
  const [subs, setSubs] = useState<AdminSub[]>([]);
  const [loadingSubs, setLoadingSubs] = useState(false);

  const PER_PAGE = 25;

  const guard = async (res: Response) => {
    if (res.status === 403) {
      setForbidden(true);
      return null;
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || body.error || `Request failed (${res.status})`);
      return null;
    }
    return res.json();
  };

  /* ---- loaders ---- */

  const loadOverview = useCallback(async () => {
    setLoadingOverview(true);
    setError("");
    try {
      const data = await guard(await apiFetch("/api/admin/overview"));
      if (data) setOverview(data);
    } catch {
      setError("Network error.");
    }
    setLoadingOverview(false);
  }, []);

  const loadCompanies = useCallback(async (page: number, q: string) => {
    setLoadingCompanies(true);
    setError("");
    try {
      const data = await guard(
        await apiFetch(`/api/admin/companies?page=${page}&per_page=${PER_PAGE}&q=${encodeURIComponent(q)}`)
      );
      if (data) {
        setCompanies(data.companies || []);
        setCompanyTotal(data.total || 0);
      }
    } catch {
      setError("Network error.");
    }
    setLoadingCompanies(false);
  }, []);

  const loadUsers = useCallback(async (page: number, q: string) => {
    setLoadingUsers(true);
    setError("");
    try {
      const data = await guard(
        await apiFetch(`/api/admin/users?page=${page}&per_page=${PER_PAGE}&q=${encodeURIComponent(q)}`)
      );
      if (data) {
        setUsers(data.users || []);
        setUserTotal(data.total || 0);
      }
    } catch {
      setError("Network error.");
    }
    setLoadingUsers(false);
  }, []);

  const loadRuns = useCallback(async (page: number) => {
    setLoadingRuns(true);
    setError("");
    try {
      const data = await guard(await apiFetch(`/api/admin/payroll-runs?page=${page}&per_page=${PER_PAGE}`));
      if (data) {
        setRuns(data.runs || []);
        setRunTotal(data.total || 0);
      }
    } catch {
      setError("Network error.");
    }
    setLoadingRuns(false);
  }, []);

  const loadSubs = useCallback(async () => {
    setLoadingSubs(true);
    setError("");
    try {
      const data = await guard(await apiFetch("/api/admin/subscriptions"));
      if (data) setSubs(data.subscriptions || []);
    } catch {
      setError("Network error.");
    }
    setLoadingSubs(false);
  }, []);

  useEffect(() => {
    if (tab === "Overview") loadOverview();
    if (tab === "Companies") loadCompanies(companyPage, companyQuery);
    if (tab === "Users") loadUsers(userPage, userQuery);
    if (tab === "Payroll") loadRuns(runPage);
    if (tab === "Subscriptions") loadSubs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, companyPage, userPage, runPage]);

  /* ---- actions ---- */

  const openCompany = async (id: number) => {
    setLoadingDetail(id);
    try {
      const data = await guard(await apiFetch(`/api/admin/companies/${id}`));
      if (data) setDetail(data);
    } catch {
      setError("Network error.");
    }
    setLoadingDetail(null);
  };

  const toggleCompany = async (c: AdminCompany) => {
    const data = await guard(
      await apiFetch(`/api/admin/companies/${c.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !c.is_active }),
      })
    );
    if (data) {
      loadCompanies(companyPage, companyQuery);
      if (detail?.company.id === c.id) openCompany(c.id);
    }
  };

  const patchUser = async (u: AdminUser, patch: Record<string, unknown>) => {
    setBusyUser(u.id);
    const data = await guard(
      await apiFetch(`/api/admin/users/${u.id}`, { method: "PATCH", body: JSON.stringify(patch) })
    );
    setBusyUser(null);
    if (data) loadUsers(userPage, userQuery);
  };

  const deleteUser = async (u: AdminUser) => {
    const sure = window.confirm(
      `Permanently DELETE ${u.email}?\n\nTheir account is removed and the email becomes free to register again. ` +
      `(To block them but keep the account, use Disable instead.)`
    );
    if (!sure) return;
    setBusyUser(u.id);
    const data = await guard(await apiFetch(`/api/admin/users/${u.id}`, { method: "DELETE" }));
    setBusyUser(null);
    if (data) loadUsers(userPage, userQuery);
  };

  const setPlanOverride = async (companyId: number, plan: string) => {
    const data = await guard(
      await apiFetch(`/api/admin/companies/${companyId}`, {
        method: "PATCH",
        body: JSON.stringify({ plan_override: plan }),
      })
    );
    if (data) openCompany(companyId);
  };

  const genResetLink = async (u: AdminUser) => {
    setBusyUser(u.id);
    setResetLink(null);
    const data = await guard(await apiFetch(`/api/admin/users/${u.id}/reset-link`, { method: "POST" }));
    setBusyUser(null);
    if (data?.reset_url) {
      setResetLink({ userId: u.id, url: data.reset_url });
      try {
        await navigator.clipboard.writeText(data.reset_url);
      } catch {
        /* clipboard unavailable — link is displayed */
      }
    }
  };

  /* ---- forbidden screen ---- */

  if (forbidden) {
    return (
      <AppLayout active="Admin">
        <div className="max-w-xl mx-auto text-center py-24">
          <ShieldAlert size={40} className="mx-auto text-destructive mb-4" />
          <h1 className="text-2xl font-extrabold tracking-tight mb-2">Admin access required</h1>
          <p className="text-muted-foreground">
            This portal is reserved for the platform owner. Your account is not on the
            platform admin list. If it should be, add your email to the
            <span className="font-mono text-sm"> PLATFORM_ADMIN_EMAILS </span>
            environment variable on the backend, then sign out and back in.
          </p>
        </div>
      </AppLayout>
    );
  }

  const pager = (page: number, total: number, setPage: (p: number) => void) => {
    const pages = Math.max(1, Math.ceil(total / PER_PAGE));
    return (
      <div className="flex items-center gap-3 justify-end mt-4 text-sm text-muted-foreground">
        <span>
          Page {page} of {pages} · {total} total
        </span>
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          <ChevronLeft size={14} />
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
          <ChevronRight size={14} />
        </Button>
      </div>
    );
  };

  const searchBox = (value: string, onChange: (v: string) => void, onSubmit: () => void, placeholder: string) => (
    <form
      className="flex items-center gap-2 mb-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="relative flex-1 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-card text-sm outline-none focus:border-primary"
        />
      </div>
      <Button type="submit" variant="outline" size="sm">
        Search
      </Button>
    </form>
  );

  const spinner = (
    <div className="flex items-center gap-3 text-muted-foreground py-10 justify-center">
      <Loader2 className="animate-spin" size={20} /> Loading…
    </div>
  );

  return (
    <AppLayout active="Admin">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">Admin Portal</h1>
            <p className="text-muted-foreground mt-1">Platform-wide visibility and controls</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (tab === "Overview") loadOverview();
              if (tab === "Companies") loadCompanies(companyPage, companyQuery);
              if (tab === "Users") loadUsers(userPage, userQuery);
              if (tab === "Payroll") loadRuns(runPage);
              if (tab === "Subscriptions") loadSubs();
            }}
          >
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border mb-6 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-semibold border-b-2 whitespace-nowrap transition-colors ${
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {error && (
          <div className="p-3 rounded-xl text-sm mb-6 border border-destructive/30 bg-destructive/5 text-destructive">
            {error}
          </div>
        )}

        {/* ---------- OVERVIEW ---------- */}
        {tab === "Overview" && (
          <>
            {loadingOverview && spinner}
            {!loadingOverview && overview && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  {[
                    { label: "Companies", value: overview.companies.total, sub: `${overview.companies.active} active` },
                    { label: "Users", value: overview.users.total, sub: `${overview.users.verified} verified` },
                    { label: "New users (30d)", value: overview.users.new_last_30d, sub: `${overview.users.new_last_7d} this week` },
                    { label: "Payroll runs", value: overview.payroll_runs.total, sub: `${overview.payroll_runs.finalized} finalized` },
                  ].map((s) => (
                    <div key={s.label} className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                      <div className="text-sm text-muted-foreground">{s.label}</div>
                      <div className="text-3xl font-extrabold tracking-tight mt-1">{s.value}</div>
                      <div className="text-xs text-muted-foreground mt-1">{s.sub}</div>
                    </div>
                  ))}
                </div>

                <h2 className="text-lg font-bold mb-3">Recent signups</h2>
                <div className="rounded-2xl border border-border bg-card shadow-sm overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-muted-foreground border-b border-border">
                        <th className="px-4 py-3 font-semibold">Name</th>
                        <th className="px-4 py-3 font-semibold">Email</th>
                        <th className="px-4 py-3 font-semibold">Company</th>
                        <th className="px-4 py-3 font-semibold">Verified</th>
                        <th className="px-4 py-3 font-semibold">Joined</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.recent_signups.map((u) => (
                        <tr key={u.id} className="border-b border-border last:border-0">
                          <td className="px-4 py-3 font-medium">{u.first_name} {u.last_name}</td>
                          <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                          <td className="px-4 py-3">{u.company_name}</td>
                          <td className="px-4 py-3">{statusPill(u.email_verified, "Verified", "Unverified")}</td>
                          <td className="px-4 py-3 text-muted-foreground">{fmtDate(u.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        {/* ---------- COMPANIES ---------- */}
        {tab === "Companies" && (
          <>
            {searchBox(companyQuery, setCompanyQuery, () => { setCompanyPage(1); loadCompanies(1, companyQuery); }, "Search companies…")}
            {loadingCompanies && spinner}
            {!loadingCompanies && (
              <div className="rounded-2xl border border-border bg-card shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border">
                      <th className="px-4 py-3 font-semibold">Company</th>
                      <th className="px-4 py-3 font-semibold">Users</th>
                      <th className="px-4 py-3 font-semibold">Stripe</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold">Created</th>
                      <th className="px-4 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {companies.map((c) => (
                      <tr key={c.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3">
                          <div className="font-medium">{c.name}</div>
                          <div className="text-xs text-muted-foreground">{c.slug}</div>
                        </td>
                        <td className="px-4 py-3 flex items-center gap-1.5">
                          <UsersIcon size={14} className="text-muted-foreground" /> {c.user_count ?? 0}
                        </td>
                        <td className="px-4 py-3">{statusPill(!!c.stripe_customer_id, "Customer", "None")}</td>
                        <td className="px-4 py-3">{statusPill(c.is_active, "Active", "Suspended")}</td>
                        <td className="px-4 py-3 text-muted-foreground">{fmtDate(c.created_at)}</td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <Button variant="outline" size="sm" className="mr-2" onClick={() => openCompany(c.id)}>
                            {loadingDetail === c.id ? <Loader2 size={13} className="animate-spin" /> : "View"}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className={c.is_active ? "text-destructive border-destructive/40" : "text-primary border-primary/40"}
                            onClick={() => toggleCompany(c)}
                          >
                            {c.is_active ? "Suspend" : "Reactivate"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {companies.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No companies found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {pager(companyPage, companyTotal, setCompanyPage)}

            {detail && (
              <div className="mt-6 rounded-2xl border border-primary/30 bg-primary/5 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <Building2 size={20} className="text-primary" />
                    <div>
                      <div className="font-bold text-lg">{detail.company.name}</div>
                      <div className="text-xs text-muted-foreground">
                        Subscription: <span className="font-semibold capitalize">{detail.subscription.status}</span>
                        {detail.subscription.plan && ` · ${PLAN_LABEL[detail.subscription.plan] || detail.subscription.plan}`}
                        {detail.subscription.current_period_end && ` · renews ${fmtDate(detail.subscription.current_period_end)}`}
                        {detail.company.plan_override && (
                          <span className="ml-2 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                            Manual grant: {PLAN_LABEL[detail.company.plan_override] || detail.company.plan_override}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-xs text-muted-foreground" title="Grant plan access without a Stripe subscription (comped account / offline payment). 'None' means access is controlled by Stripe.">
                      Manual plan
                    </label>
                    <select
                      value={detail.company.plan_override || ""}
                      onChange={(e) => setPlanOverride(detail.company.id, e.target.value)}
                      className="rounded-md border border-border bg-card px-2 py-1 text-xs outline-none focus:border-primary"
                    >
                      <option value="">None (Stripe controls)</option>
                      <option value="combo">Combo</option>
                      <option value="payroll_only">Payroll Only</option>
                      <option value="bookkeeping_only">Bookkeeping Only</option>
                    </select>
                    <Button variant="outline" size="sm" onClick={() => setDetail(null)}>Close</Button>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="font-semibold text-sm mb-2">Team ({detail.users.length})</h3>
                    <div className="space-y-2">
                      {detail.users.map((u) => (
                        <div key={u.id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                          <div>
                            <div className="font-medium">{u.first_name} {u.last_name} <span className="text-xs text-muted-foreground">({u.role})</span></div>
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                          </div>
                          {statusPill(u.is_active, "Active", "Disabled")}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm mb-2">Recent payroll runs</h3>
                    {detail.payroll_runs.length === 0 && (
                      <div className="text-sm text-muted-foreground">No payroll runs yet.</div>
                    )}
                    <div className="space-y-2">
                      {detail.payroll_runs.map((r) => (
                        <div key={r.run_id} className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm">
                          <div>
                            <div className="font-mono text-xs">{r.run_id.slice(0, 18)}…</div>
                            <div className="text-xs text-muted-foreground">{fmtEpoch(r.created_at)}</div>
                          </div>
                          {statusPill(r.finalized, "Finalized", r.status || "Draft")}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ---------- USERS ---------- */}
        {tab === "Users" && (
          <>
            {searchBox(userQuery, setUserQuery, () => { setUserPage(1); loadUsers(1, userQuery); }, "Search by name or email…")}
            {resetLink && (
              <div className="p-3 rounded-xl text-sm mb-4 border border-primary/30 bg-primary/5">
                <span className="font-semibold">Reset link generated</span> (copied to clipboard, expires in 1 hour):
                <div className="font-mono text-xs mt-1 break-all">{resetLink.url}</div>
              </div>
            )}
            {loadingUsers && spinner}
            {!loadingUsers && (
              <div className="rounded-2xl border border-border bg-card shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border">
                      <th className="px-4 py-3 font-semibold">User</th>
                      <th className="px-4 py-3 font-semibold">Company</th>
                      <th className="px-4 py-3 font-semibold">Role</th>
                      <th className="px-4 py-3 font-semibold">Verified</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3">
                          <div className="font-medium">
                            {u.first_name} {u.last_name}
                            {u.is_platform_admin && (
                              <span className="ml-2 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/10 text-primary">Platform admin</span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">{u.email}</div>
                        </td>
                        <td className="px-4 py-3">{u.company_name}</td>
                        <td className="px-4 py-3">
                          <select
                            value={u.role}
                            disabled={busyUser === u.id}
                            onChange={(e) => patchUser(u, { role: e.target.value })}
                            className="rounded-md border border-border bg-card px-2 py-1 text-xs outline-none focus:border-primary"
                          >
                            <option value="admin">admin</option>
                            <option value="manager">manager</option>
                            <option value="viewer">viewer</option>
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          {u.email_verified ? (
                            statusPill(true, "Verified", "")
                          ) : (
                            <Button variant="outline" size="sm" disabled={busyUser === u.id}
                              onClick={() => patchUser(u, { email_verified: true })}>
                              Mark verified
                            </Button>
                          )}
                        </td>
                        <td className="px-4 py-3">{statusPill(u.is_active, "Active", "Disabled")}</td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <Button variant="outline" size="sm" className="mr-2"
                            title={u.is_platform_admin ? "Revoke platform admin" : "Make platform admin"}
                            disabled={busyUser === u.id}
                            onClick={() => patchUser(u, { is_platform_admin: !u.is_platform_admin })}>
                            {u.is_platform_admin ? <ShieldOff size={13} /> : <ShieldCheck size={13} />}
                          </Button>
                          <Button variant="outline" size="sm" className="mr-2" title="Generate password reset link"
                            disabled={busyUser === u.id} onClick={() => genResetLink(u)}>
                            <KeyRound size={13} />
                          </Button>
                          <Button
                            variant="outline" size="sm" className="mr-2" disabled={busyUser === u.id}
                            title={u.is_active ? "Suspend (reversible — account kept, sign-in blocked)" : "Re-enable account"}
                            onClick={() => patchUser(u, { is_active: !u.is_active })}
                          >
                            {busyUser === u.id ? <Loader2 size={13} className="animate-spin" /> : u.is_active ? "Disable" : "Enable"}
                          </Button>
                          <Button
                            variant="outline" size="sm" disabled={busyUser === u.id}
                            className="text-destructive border-destructive/40"
                            title="Delete permanently (frees the email for re-registration)"
                            onClick={() => deleteUser(u)}
                          >
                            <Trash2 size={13} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {users.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No users found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {pager(userPage, userTotal, setUserPage)}
          </>
        )}

        {/* ---------- PAYROLL ---------- */}
        {tab === "Payroll" && (
          <>
            {loadingRuns && spinner}
            {!loadingRuns && (
              <div className="rounded-2xl border border-border bg-card shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border">
                      <th className="px-4 py-3 font-semibold">Run</th>
                      <th className="px-4 py-3 font-semibold">Company</th>
                      <th className="px-4 py-3 font-semibold">Created</th>
                      <th className="px-4 py-3 font-semibold">Net total</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.run_id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3 font-mono text-xs">{r.run_id.slice(0, 22)}…</td>
                        <td className="px-4 py-3">{r.company_name || `#${r.company_id}`}</td>
                        <td className="px-4 py-3 text-muted-foreground">{fmtEpoch(r.created_at)}</td>
                        <td className="px-4 py-3">{r.total_net != null ? `$${r.total_net.toFixed(2)}` : "—"}</td>
                        <td className="px-4 py-3">{statusPill(r.finalized, "Finalized", r.status || "Draft")}</td>
                      </tr>
                    ))}
                    {runs.length === 0 && (
                      <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No payroll runs yet.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            {pager(runPage, runTotal, setRunPage)}
          </>
        )}

        {/* ---------- SUBSCRIPTIONS ---------- */}
        {tab === "Subscriptions" && (
          <>
            {loadingSubs && spinner}
            {!loadingSubs && (
              <div className="rounded-2xl border border-border bg-card shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground border-b border-border">
                      <th className="px-4 py-3 font-semibold">Company</th>
                      <th className="px-4 py-3 font-semibold">Plan</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold">Renews</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subs.map((s) => (
                      <tr key={s.company_id} className="border-b border-border last:border-0">
                        <td className="px-4 py-3 font-medium">{s.company_name}</td>
                        <td className="px-4 py-3">{s.plan ? PLAN_LABEL[s.plan] || s.plan : "—"}</td>
                        <td className="px-4 py-3">
                          <span className={`capitalize font-semibold ${
                            ["active", "trialing"].includes(s.status) ? "text-primary"
                              : s.status === "none" ? "text-muted-foreground" : "text-destructive"
                          }`}>
                            {s.status}
                          </span>
                          {s.detail && <div className="text-xs text-muted-foreground mt-0.5">{s.detail}</div>}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{fmtDate(s.current_period_end)}</td>
                      </tr>
                    ))}
                    {subs.length === 0 && (
                      <tr><td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                        No companies have a Stripe customer yet.
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default Admin;
