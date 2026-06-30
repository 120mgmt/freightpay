import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  LayoutDashboard, DollarSign, Users, BookOpen,
  FileText, CreditCard, Settings, LogOut,
} from "lucide-react";

const NAV = [
  { label: "Dashboard",   icon: LayoutDashboard, to: "/dashboard" },
  { label: "Settlements", icon: DollarSign,       to: "/settlements" },
  { label: "Payroll",     icon: Users,            to: "/payroll" },
  { label: "Bookkeeping", icon: BookOpen,         to: "/bookkeeping" },
  { label: "Reports",     icon: FileText,         to: "/reports" },
  { label: "Billing",     icon: CreditCard,       to: "/billing" },
];

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
      <header
        className="h-[80px] flex items-center border-b border-border px-6"
        style={{ background: "rgba(8,13,17,0.7)", backdropFilter: "blur(24px)" }}
      >
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
          <div
            className="h-9 w-9 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
          >
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <button
            onClick={handleLogout}
            className="text-muted-foreground hover:text-white transition-colors"
            title="Sign out"
          >
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className="hidden md:flex flex-col w-60 border-r border-border p-4 gap-1 min-h-[calc(100vh-80px)]"
          style={{ background: "rgba(14,20,27,0.5)" }}
        >
          {NAV.map((item) => {
            const isActive = active === item.label;
            return (
              <Link
                key={item.label}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "text-white"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-elevated"
                }`}
                style={isActive ? { background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" } : {}}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            );
          })}
          <div className="mt-auto">
            <Link
              to="/settings"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-surface-elevated transition-colors"
            >
              <Settings size={18} />
              Settings
            </Link>
          </div>
        </aside>

        {/* Page content */}
        <main className="flex-1 p-6 lg:p-10">{children}</main>
      </div>
    </div>
  );
};

export default AppLayout;
