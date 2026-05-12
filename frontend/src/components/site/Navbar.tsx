import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const links = [
  { label: "Platform", href: "#platform" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "/docs" },
];

export const Navbar = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuth();

  const handleLinkClick = (href: string) => {
    setOpen(false);
    if (href.startsWith("/")) {
      navigate(href);
    } else {
      // Scroll to section on same page
      const el = document.querySelector(href);
      if (el) el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-[80px] flex items-center bg-[rgba(8,13,17,0.7)] backdrop-blur-[24px] border-b border-border">
      <nav className="container mx-auto flex items-center justify-between px-6">
        {/* Logo */}
        <a href="/" className="flex items-center" onClick={(e) => { e.preventDefault(); navigate("/"); }}>
          <img src="/Logo.png" alt="LedgerHaul" className="h-20 w-auto" />
        </a>

        {/* Desktop nav pill */}
        <div className="hidden md:flex items-center gap-1 bg-surface/60 backdrop-blur-md border border-border rounded-full px-2 py-1.5">
          {links.map((l) => (
            <button
              key={l.href}
              onClick={() => handleLinkClick(l.href)}
              className="px-5 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground rounded-full hover:bg-surface-elevated transition-colors"
            >
              {l.label}
            </button>
          ))}
        </div>

        {/* Desktop buttons */}
        <div className="hidden md:flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="text-[rgb(183,197,215)] hover:text-white text-[14px] font-medium px-3"
                onClick={() => navigate("/dashboard")}
              >
                Dashboard
              </Button>
              <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold cursor-pointer"
                style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
                onClick={() => navigate("/dashboard")}
                title={user?.email}
              >
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="text-[rgb(183,197,215)] hover:text-white text-[14px] font-medium px-3"
                onClick={() => navigate("/signin")}
              >
                Sign in
              </Button>
              <Button
                size="sm"
                style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 10, boxShadow: "0 0 20px rgba(54,211,148,0.3)", fontWeight: 500, fontSize: 14 }}
                onClick={() => navigate("/register")}
              >
                Get started
              </Button>
            </>
          )}
        </div>

        {/* Mobile */}
        <button className="md:hidden text-foreground" onClick={() => setOpen(!open)} aria-label="Menu">
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      {open && (
        <div className="md:hidden absolute top-[65px] inset-x-0 border-t border-border bg-[rgba(8,13,17,0.95)] backdrop-blur-xl">
          <div className="container mx-auto px-6 py-4 flex flex-col gap-2">
            {links.map((l) => (
              <button key={l.href} onClick={() => handleLinkClick(l.href)} className="py-2 text-sm text-muted-foreground hover:text-foreground text-left">
                {l.label}
              </button>
            ))}
            <div className="flex gap-2 pt-2">
              {isAuthenticated ? (
                <>
                  <Button variant="secondary" size="sm" className="flex-1 text-sm" onClick={() => { setOpen(false); navigate("/dashboard"); }}>
                    Dashboard
                  </Button>
                  <Button size="sm" className="flex-1 text-sm" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
                    onClick={() => { logout(); setOpen(false); }}>
                    Sign out
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="secondary" size="sm" className="flex-1 text-sm" onClick={() => { setOpen(false); navigate("/signin"); }}>
                    Sign in
                  </Button>
                  <Button size="sm" className="flex-1 text-sm" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}
                    onClick={() => { setOpen(false); navigate("/register"); }}>
                    Get started
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
