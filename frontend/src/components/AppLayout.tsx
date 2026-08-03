import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, DollarSign, Users, BookOpen,
  FileText, CreditCard, Settings, LogOut, ShieldCheck, Receipt,
} from "lucide-react";

const NAV = [
  { label: "Dashboard",   icon: LayoutDashboard, to: "/dashboard" },
  { label: "Settlements", icon: DollarSign,       to: "/settlements" },
  { label: "Payroll",     icon: Users,            to: "/payroll" },
  { label: "Bookkeeping", icon: BookOpen,         to: "/bookkeeping" },
  { label: "Invoices",    icon: Receipt,          to: "/invoices" },
  { label: "Reports",     icon: FileText,         to: "/reports" },
  { label: "Billing",     icon: CreditCard,       to: "/billing" },
];

const ADMIN_ITEM = { label: "Admin", icon: ShieldCheck, to: "/admin" };

interface AppLayoutProps {
  children: React.ReactNode;
  active: string;
}

const AppLayout = ({ children, active }: AppLayoutProps) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header className="h-[84px] flex items-center border-b border-border px-4 sm:px-6 bg-surface/85 backdrop-blur-md sticky top-0 z-30">
        <Link to="/dashboard" className="flex items-center shrink-0">
          <img src="/logo-light.png" alt="LedgerHaul" className="h-12 sm:h-14 w-auto" />
        </Link>
        <div className="ml-auto flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <div className="text-sm font-semibold text-foreground">
              {user?.first_name} {user?.last_name}
            </div>
            <div className="text-xs text-muted-foreground">{user?.email}</div>
          </div>
          {user?.avatar_url ? (
            <img
              src={user.avatar_url}
              alt="Profile"
              className="h-9 w-9 rounded-full object-cover border border-border"
            />
          ) : (
            <div className="h-9 w-9 rounded-full flex items-center justify-center text-xs font-bold bg-primary text-primary-foreground">
              {user?.first_name?.[0]}{user?.last_name?.[0]}
            </div>
          )}
          <button
            onClick={handleLogout}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Sign out"
          >
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {/* Mobile nav */}
      <nav className="md:hidden flex overflow-x-auto border-b border-border bg-surface px-2">
        {[
          ...NAV,
          ...(user?.is_platform_admin ? [ADMIN_ITEM] : []),
          { label: "Settings", icon: Settings, to: "/settings" },
        ].map((item) => {
          const isActive = active === item.label;
          return (
            <Link
              key={item.label}
              to={item.to}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-medium whitespace-nowrap border-b-2 transition-colors ${
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <item.icon size={15} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden md:flex flex-col w-60 border-r border-border p-4 gap-1 min-h-[calc(100vh-84px)] bg-surface">
          {NAV.map((item) => {
            const isActive = active === item.label;
            return (
              <Link
                key={item.label}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            );
          })}
          {user?.is_platform_admin && (
            <Link
              to={ADMIN_ITEM.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active === "Admin"
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <ShieldCheck size={18} />
              Admin
            </Link>
          )}
          <div className="mt-auto">
            <Link
              to="/settings"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active === "Settings"
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <Settings size={18} />
              Settings
            </Link>
          </div>
        </aside>

        {/* Page content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-10">{children}</main>
      </div>
    </div>
  );
};

export default AppLayout;
