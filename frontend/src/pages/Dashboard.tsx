import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard, DollarSign, BookOpen, Users, FileText,
  Settings, LogOut, TrendingUp, CreditCard, ArrowUpRight,
} from "lucide-react";

const stats = [
  { label: "Active Drivers", value: "24", change: "+3 this month", icon: Users },
  { label: "Settlements This Week", value: "$28,412", change: "+12.4%", icon: DollarSign },
  { label: "Pending Payouts", value: "7", change: "3 processing", icon: CreditCard },
  { label: "Revenue MTD", value: "$142,800", change: "+8.2% vs last month", icon: TrendingUp },
];

const quickActions = [
  { label: "Run Settlement", desc: "Calculate and post a new contractor settlement", icon: DollarSign },
  { label: "Process Payroll", desc: "Run payroll for your active drivers", icon: Users },
  { label: "View Ledger", desc: "Review journal entries and account balances", icon: BookOpen },
  { label: "Generate Reports", desc: "P&L, balance sheet, and cash flow reports", icon: FileText },
];

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header className="h-[80px] flex items-center border-b border-border px-6"
        style={{ background: "rgba(8,13,17,0.7)", backdropFilter: "blur(24px)" }}>
        <Link to="/" className="flex items-center">
          <img src="/Logo.png" alt="LedgerHaul" className="h-20 w-auto" />
        </Link>
        <div className="ml-auto flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <div className="text-sm text-white font-medium">
              {user?.first_name} {user?.last_name}
            </div>
            <div className="text-xs text-muted-foreground">{user?.email}</div>
          </div>
          <div className="h-9 w-9 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <button onClick={handleLogout} className="text-muted-foreground hover:text-white transition-colors" title="Sign out">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden md:flex flex-col w-60 border-r border-border p-4 gap-1 min-h-[calc(100vh-80px)]"
          style={{ background: "rgba(14,20,27,0.5)" }}>
          {[
            { icon: LayoutDashboard, label: "Dashboard", active: true },
            { icon: DollarSign, label: "Settlements" },
            { icon: Users, label: "Payroll" },
            { icon: BookOpen, label: "Bookkeeping" },
            { icon: FileText, label: "Reports" },
            { icon: CreditCard, label: "Billing" },
          ].map((item) => (
            <button
              key={item.label}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                item.active
                  ? "text-white"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-elevated"
              }`}
              style={item.active ? { background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" } : {}}
            >
              <item.icon size={18} />
              {item.label}
            </button>
          ))}
          <div className="mt-auto">
            <button className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-surface-elevated transition-colors w-full">
              <Settings size={18} />
              Settings
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 p-6 lg:p-10">
          <div className="max-w-6xl">
            {/* Welcome */}
            <div className="mb-8">
              <h1 className="text-2xl font-semibold text-white mb-1">
                Welcome back, {user?.first_name} 👋
              </h1>
              <p className="text-muted-foreground">
                Here's what's happening with your operations today.
              </p>
            </div>

            {/* Stats grid */}
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
              {stats.map((s) => (
                <div key={s.label} className="rounded-xl border border-border p-5"
                  style={{ background: "rgba(19,27,37,0.6)" }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">{s.label}</span>
                    <s.icon size={16} className="text-muted-foreground" />
                  </div>
                  <div className="text-2xl font-semibold text-white mb-1">{s.value}</div>
                  <div className="text-xs" style={{ color: "rgb(54,211,148)" }}>{s.change}</div>
                </div>
              ))}
            </div>

            {/* Quick actions */}
            <h2 className="text-lg font-semibold text-white mb-4">Quick Actions</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {quickActions.map((a) => (
                <button key={a.label}
                  className="group rounded-xl border border-border p-5 text-left hover:border-primary/40 transition-all"
                  style={{ background: "rgba(19,27,37,0.6)" }}>
                  <div className="flex items-start justify-between">
                    <div className="h-10 w-10 rounded-lg flex items-center justify-center mb-3"
                      style={{ background: "rgba(54,211,148,0.1)", border: "1px solid rgba(54,211,148,0.3)" }}>
                      <a.icon size={18} style={{ color: "rgb(54,211,148)" }} />
                    </div>
                    <ArrowUpRight size={16} className="text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                  <div className="text-white font-medium mb-1">{a.label}</div>
                  <div className="text-sm text-muted-foreground">{a.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Dashboard;
