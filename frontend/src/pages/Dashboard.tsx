import { useAuth } from "@/contexts/AuthContext";
import AppLayout from "@/components/AppLayout";
import { useNavigate } from "react-router-dom";
import {
  DollarSign, BookOpen, Users, FileText,
  TrendingUp, CreditCard, ArrowUpRight,
} from "lucide-react";

const stats = [
  { label: "Active Drivers",         value: "24",      change: "+3 this month",         icon: Users      },
  { label: "Settlements This Week",  value: "$28,412", change: "+12.4%",                icon: DollarSign },
  { label: "Pending Payouts",        value: "7",       change: "3 processing",           icon: CreditCard },
  { label: "Revenue MTD",            value: "$142,800",change: "+8.2% vs last month",    icon: TrendingUp },
];

const quickActions = [
  { label: "Run Settlement",    desc: "Calculate and post a new contractor settlement", icon: DollarSign, to: "/settlements" },
  { label: "Process Payroll",   desc: "Run payroll for your active drivers",            icon: Users,      to: "/payroll"     },
  { label: "View Ledger",       desc: "Review journal entries and account balances",    icon: BookOpen,   to: "/bookkeeping" },
  { label: "Generate Reports",  desc: "P&L, balance sheet, and cash flow reports",     icon: FileText,   to: "/reports"     },
];

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <AppLayout active="Dashboard">
      <div className="max-w-6xl">
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
            <button
              key={a.label}
              onClick={() => navigate(a.to)}
              className="group rounded-xl border border-border p-5 text-left hover:border-primary/40 transition-all"
              style={{ background: "rgba(19,27,37,0.6)" }}
            >
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
    </AppLayout>
  );
};

export default Dashboard;
