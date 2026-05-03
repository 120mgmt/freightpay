const cols = [
  {
    title: "Product",
    links: ["Payroll", "Settlements", "Bookkeeping", "Subscriptions", "Integrations"],
  },
  {
    title: "Developers",
    links: ["API Reference", "Webhooks", "SDKs", "Changelog", "Status"],
  },
  {
    title: "Company",
    links: ["About", "Customers", "Careers", "Blog", "Contact"],
  },
  {
    title: "Legal",
    links: ["Terms", "Privacy", "Security", "DPA", "SOC 2"],
  },
];

export const Footer = () => {
  return (
    <footer className="border-t border-border" style={{ background: "rgba(17,22,29,0.3)" }}>
      <div className="container mx-auto px-6 py-16">
        <div className="grid md:grid-cols-6 gap-10">

          {/* Brand column */}
          <div className="md:col-span-2">
            <div className="mb-4">
              <img src="/Logo.png" alt="LedgerHaul" className="h-14 w-auto" />
            </div>
            <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
              Production backend service for payroll, settlements, bookkeeping, and
              subscriptions in trucking and logistics. Financial clarity for every mile.
            </p>
            <div className="mt-6 inline-flex items-center gap-2 text-xs font-mono text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
              All systems operational
            </div>
          </div>

          {/* Link columns */}
          {cols.map((c) => (
            <div key={c.title}>
              <h4 className="text-white font-semibold text-sm mb-4">{c.title}</h4>
              <ul className="space-y-2.5">
                {c.links.map((l) => (
                  <li key={l}>
                    <a href="#" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                      {l}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-16 pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} LedgerHaul, Inc. All rights reserved.
          </p>
          <p className="text-xs text-muted-foreground font-mono">
            api.ledgerhaul.com · v3.1
          </p>
        </div>
      </div>
    </footer>
  );
};