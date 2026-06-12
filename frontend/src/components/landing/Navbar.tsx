import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const links = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Features", href: "#features" },
  { label: "Compare", href: "#compare" },
  { label: "Pricing", href: "#pricing" },
];

export const Wordmark = ({ className = "" }: { className?: string }) => (
  <span className={`text-[21px] font-extrabold tracking-tight leading-none ${className}`}>
    Ledger<span className="text-primary">Haul</span>
  </span>
);

export const Navbar = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const handleLinkClick = (href: string) => {
    setOpen(false);
    if (href.startsWith("/")) {
      navigate(href);
    } else {
      document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <header className="fixed top-0 inset-x-0 z-40 h-16 flex items-center border-b border-border bg-[hsl(var(--background)/0.88)] backdrop-blur-md">
      <nav className="w-full max-w-7xl mx-auto flex items-center justify-between px-6">
        <a
          href="/"
          className="flex items-center"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
            window.scrollTo({ top: 0 });
          }}
          aria-label="LedgerHaul home"
        >
          <Wordmark />
        </a>

        <div className="hidden md:flex items-center gap-1">
          {links.map((l) => (
            <button
              key={l.href}
              onClick={() => handleLinkClick(l.href)}
              className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              {l.label}
            </button>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          {isAuthenticated ? (
            <>
              <button
                onClick={() => navigate("/dashboard")}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                Dashboard
              </button>
              <button
                onClick={() => navigate("/dashboard")}
                title={user?.email}
                className="h-9 w-9 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center"
              >
                {user?.first_name?.[0]}
                {user?.last_name?.[0]}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate("/signin")}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                Sign in
              </button>
              <button
                onClick={() => navigate("/register")}
                className="rounded-full bg-primary text-primary-foreground text-sm font-semibold px-5 py-2.5 hover:bg-[hsl(var(--primary-dim))] active:scale-[0.98] transition-all"
              >
                Start free trial
              </button>
            </>
          )}
        </div>

        <button
          className="md:hidden text-foreground"
          onClick={() => setOpen(!open)}
          aria-label="Menu"
        >
          {open ? <X size={22} strokeWidth={2} /> : <Menu size={22} strokeWidth={2} />}
        </button>
      </nav>

      {open && (
        <div className="md:hidden absolute top-16 inset-x-0 border-b border-border bg-[hsl(var(--background)/0.97)] backdrop-blur-xl">
          <div className="px-6 py-4 flex flex-col gap-1">
            {links.map((l) => (
              <button
                key={l.href}
                onClick={() => handleLinkClick(l.href)}
                className="py-2.5 text-[15px] font-medium text-foreground text-left"
              >
                {l.label}
              </button>
            ))}
            <div className="flex gap-3 pt-3">
              {isAuthenticated ? (
                <button
                  className="flex-1 rounded-full bg-primary text-primary-foreground text-sm font-semibold py-2.5"
                  onClick={() => {
                    setOpen(false);
                    navigate("/dashboard");
                  }}
                >
                  Dashboard
                </button>
              ) : (
                <>
                  <button
                    className="flex-1 rounded-full border border-border text-sm font-semibold py-2.5"
                    onClick={() => {
                      setOpen(false);
                      navigate("/signin");
                    }}
                  >
                    Sign in
                  </button>
                  <button
                    className="flex-1 rounded-full bg-primary text-primary-foreground text-sm font-semibold py-2.5"
                    onClick={() => {
                      setOpen(false);
                      navigate("/register");
                    }}
                  >
                    Start free trial
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
