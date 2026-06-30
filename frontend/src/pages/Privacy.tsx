import { Link } from "react-router-dom";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="mb-8">
    <h2 className="text-lg font-semibold text-white mb-3">{title}</h2>
    <div className="text-muted-foreground leading-relaxed space-y-3 text-sm">{children}</div>
  </div>
);

const Privacy = () => (
  <div className="min-h-screen bg-background text-foreground">
    <header className="h-[72px] flex items-center border-b border-border px-6" style={{ background: "rgba(8,13,17,0.7)", backdropFilter: "blur(24px)" }}>
      <Link to="/">
        <img src="/Logo.png" alt="LedgerHaul" className="h-16 w-auto" />
      </Link>
      <nav className="ml-auto flex gap-4 text-sm text-muted-foreground">
        <Link to="/terms" className="hover:text-white transition-colors">Terms</Link>
        <Link to="/signin" className="hover:text-white transition-colors">Sign in</Link>
      </nav>
    </header>

    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-semibold text-white mb-2">Privacy Policy</h1>
      <p className="text-muted-foreground text-sm mb-10">Last updated: June 30, 2026</p>

      <Section title="1. Information We Collect">
        <p><strong className="text-white">Account data:</strong> Name, email, company name, and password (hashed — never stored in plain text).</p>
        <p><strong className="text-white">Business data:</strong> Driver information, payroll records, settlement amounts, and financial data you enter into the Service.</p>
        <p><strong className="text-white">Usage data:</strong> Log files, IP addresses, browser type, pages visited, and timestamps — used to operate and improve the Service.</p>
        <p><strong className="text-white">Payment data:</strong> Billing is handled by Stripe. We receive only a tokenized reference; full card numbers are never transmitted to or stored by LedgerHaul.</p>
      </Section>

      <Section title="2. How We Use Your Information">
        <p>We use your information to: (a) provide and operate the Service; (b) send transactional emails (account verification, password reset, invoices); (c) respond to support requests; (d) detect and prevent fraud or abuse; (e) improve the Service through aggregate analytics.</p>
        <p>We do not sell your personal data to third parties.</p>
      </Section>

      <Section title="3. Data Sharing">
        <p>We share data only with: (a) service providers who assist in delivering the Service (e.g., Stripe for payments, Brevo for transactional email, Render for hosting) under data processing agreements; (b) law enforcement when required by valid legal process; (c) a successor entity in the event of a merger or acquisition.</p>
      </Section>

      <Section title="4. Data Retention">
        <p>We retain your account data for as long as your account is active, plus 30 days after termination. Financial records may be retained longer where required by applicable law (e.g., IRS recordkeeping requirements).</p>
      </Section>

      <Section title="5. Security">
        <p>We use industry-standard measures including TLS encryption in transit, hashed passwords (bcrypt), and access controls. No method of transmission or storage is 100% secure; we encourage you to use strong, unique passwords and enable two-factor authentication when available.</p>
      </Section>

      <Section title="6. Your Rights">
        <p>Depending on your jurisdiction, you may have the right to access, correct, or delete your personal data. To exercise these rights, email <a href="mailto:privacy@ledgerhaul.com" className="underline hover:text-white">privacy@ledgerhaul.com</a>. We will respond within 30 days.</p>
      </Section>

      <Section title="7. Cookies">
        <p>We use only technically necessary cookies and localStorage tokens for authentication. We do not use tracking or advertising cookies.</p>
      </Section>

      <Section title="8. Changes">
        <p>We may update this policy from time to time. We will notify you of material changes via email at least 14 days before they take effect.</p>
      </Section>

      <Section title="9. Contact">
        <p>Privacy questions: <a href="mailto:privacy@ledgerhaul.com" className="underline hover:text-white">privacy@ledgerhaul.com</a></p>
      </Section>
    </main>

    <footer className="border-t border-border py-8 text-center text-xs text-muted-foreground">
      © {new Date().getFullYear()} LedgerHaul, Inc. ·{" "}
      <Link to="/privacy" className="hover:text-white underline">Privacy</Link> ·{" "}
      <Link to="/terms" className="hover:text-white underline">Terms</Link>
    </footer>
  </div>
);

export default Privacy;
