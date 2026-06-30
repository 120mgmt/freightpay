import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./Reveal";

const cols = [
  {
    title: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Features", href: "#features" },
      { label: "Compare", href: "#compare" },
      { label: "Pricing", href: "#pricing" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "API docs", href: "/docs" },
      { label: "Support", href: "mailto:support@ledgerhaul.com" },
      { label: "Dashboard", href: "/dashboard" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Contact", href: "mailto:hello@ledgerhaul.com" },
      { label: "Careers", href: "mailto:jobs@ledgerhaul.com" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms", href: "/terms" },
      { label: "Privacy", href: "/privacy" },
      { label: "Security", href: "mailto:security@ledgerhaul.com" },
    ],
  },
];

/* The page's single dark color block: closing CTA + footer. */
export const Closing = () => {
  const navigate = useNavigate();

  const go = (href: string) => {
    if (href.startsWith("mailto:")) { window.location.href = href; }
    else if (href.startsWith("/")) navigate(href);
    else if (href !== "#") document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className="bg-[hsl(var(--ink))] text-white">
      {/* CTA */}
      <div className="max-w-7xl mx-auto px-6 pt-24 lg:pt-32 pb-20 text-center">
        <Reveal>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tighter leading-[1.06]">
            Financial clarity for every mile.
          </h2>
          <p className="mt-5 text-lg text-white/70 leading-relaxed max-w-xl mx-auto">
            Connect your drivers, set their pay, and run your first settlement
            this week.
          </p>
          <button
            onClick={() => navigate("/register")}
            className="group mt-9 inline-flex items-center gap-2 rounded-full bg-[hsl(var(--primary-glow))] text-[hsl(var(--ink))] text-[15px] font-bold px-8 py-4 hover:brightness-110 active:scale-[0.98] transition-all"
          >
            Start free trial
            <ArrowRight
              size={16}
              strokeWidth={2.5}
              className="transition-transform group-hover:translate-x-0.5"
            />
          </button>
        </Reveal>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-14">
          <div className="grid md:grid-cols-6 gap-10">
            <div className="md:col-span-2">
              <img src="/Logo.png" alt="LedgerHaul" className="h-16 w-auto -ml-3" />
              <p className="mt-3 text-sm text-white/60 leading-relaxed max-w-xs">
                Payroll, driver settlements, and bookkeeping for US trucking
                carriers.
              </p>
            </div>
            {cols.map((c) => (
              <div key={c.title}>
                <h4 className="font-semibold text-sm mb-4">{c.title}</h4>
                <ul className="space-y-2.5">
                  {c.links.map((l) => (
                    <li key={l.label}>
                      <button
                        onClick={() => go(l.href)}
                        className="text-sm text-white/60 hover:text-white transition-colors"
                      >
                        {l.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="mt-14 pt-7 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-3">
            <p className="text-xs text-white/50">
              © {new Date().getFullYear()} LedgerHaul, Inc. All rights reserved.
            </p>
            <p className="text-xs text-white/50">Built for American carriers.</p>
          </div>
        </div>
      </footer>
    </section>
  );
};
