import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { label: "Platform", href: "#platform" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "#docs" },
];

export const Navbar = () => {
  const [open, setOpen] = useState(false);

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-[65px] flex items-center bg-[rgba(8,13,17,0.7)] backdrop-blur-[24px] border-b border-border">
      <nav className="container mx-auto flex items-center justify-between px-6">
        {/* Logo */}
        <a href="#" className="flex items-center">
          <img src="/Logo.png" alt="LedgerHaul" className="h-10 w-auto" />
        </a>

        {/* Desktop nav pill */}
        <div className="hidden md:flex items-center gap-1 bg-surface/60 backdrop-blur-md border border-border rounded-full px-2 py-1.5">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="px-5 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground rounded-full hover:bg-surface-elevated transition-colors">
              {l.label}
            </a>
          ))}
        </div>

        {/* Desktop buttons */}
        <div className="hidden md:flex items-center gap-2">
          <Button variant="ghost" size="sm" className="text-[rgb(183,197,215)] hover:text-white text-[14px] font-medium px-3">Sign in</Button>
          <Button size="sm" style={{ background:"rgb(54,211,148)", color:"rgb(14,20,27)", borderRadius:10, boxShadow:"0 0 20px rgba(54,211,148,0.3)", fontWeight:500, fontSize:14 }}>Get started</Button>
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
              <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="py-2 text-sm text-muted-foreground hover:text-foreground">{l.label}</a>
            ))}
            <div className="flex gap-2 pt-2">
              <Button variant="secondary" size="sm" className="flex-1 text-sm">Sign in</Button>
              <Button size="sm" className="flex-1 text-sm" style={{ background:"rgb(54,211,148)", color:"rgb(14,20,27)" }}>Get started</Button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};