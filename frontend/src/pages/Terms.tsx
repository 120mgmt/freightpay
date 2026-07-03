import { Link } from "react-router-dom";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="mb-8">
    <h2 className="text-lg font-bold mb-3">{title}</h2>
    <div className="text-muted-foreground leading-relaxed space-y-3 text-sm">{children}</div>
  </div>
);

const Terms = () => (
  <div className="min-h-screen bg-background text-foreground">
    <header className="h-[80px] flex items-center border-b border-border px-6 bg-surface/85 backdrop-blur-md">
      <Link to="/">
        <img src="/logo-light.png" alt="LedgerHaul" className="h-12 w-auto" />
      </Link>
      <nav className="ml-auto flex gap-4 text-sm text-muted-foreground">
        <Link to="/privacy" className="hover:text-foreground transition-colors">Privacy</Link>
        <Link to="/signin" className="hover:text-foreground transition-colors">Sign in</Link>
      </nav>
    </header>

    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-extrabold tracking-tight mb-2">Terms of Service</h1>
      <p className="text-muted-foreground text-sm mb-10">Last updated: June 30, 2026</p>

      <Section title="1. Acceptance of Terms">
        <p>By accessing or using LedgerHaul ("Service"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.</p>
      </Section>

      <Section title="2. Description of Service">
        <p>LedgerHaul provides payroll, settlement, and bookkeeping software designed for US trucking carriers and fleet operators. Features include contractor payroll processing, driver settlements, chart of accounts management, and financial reporting.</p>
      </Section>

      <Section title="3. Account Registration">
        <p>You must provide accurate, complete, and current information when creating an account. You are responsible for maintaining the confidentiality of your credentials and for all activity that occurs under your account.</p>
      </Section>

      <Section title="4. Acceptable Use">
        <p>You agree not to: (a) use the Service for unlawful purposes; (b) attempt to gain unauthorized access to any systems; (c) transmit malicious code; (d) resell or sublicense the Service without authorization; (e) use the Service to process transactions that violate applicable law.</p>
      </Section>

      <Section title="5. Payment and Billing">
        <p>Paid plans are billed in advance on a monthly or annual basis. All fees are non-refundable except as required by law. We reserve the right to modify pricing with 30 days' notice. Stripe processes all payments — LedgerHaul does not store card data.</p>
      </Section>

      <Section title="6. Data and Privacy">
        <p>Your use of the Service is subject to our <Link to="/privacy" className="underline hover:text-foreground">Privacy Policy</Link>. You retain ownership of your data. We process it only to provide the Service.</p>
      </Section>

      <Section title="7. Limitation of Liability">
        <p>To the maximum extent permitted by law, LedgerHaul shall not be liable for any indirect, incidental, special, consequential, or punitive damages. Our total liability to you for any claims under these Terms shall not exceed the amount you paid us in the 12 months preceding the claim.</p>
      </Section>

      <Section title="8. Termination">
        <p>Either party may terminate this agreement at any time. Upon termination, your right to access the Service ceases immediately. We will retain your data for 30 days after termination, after which it may be deleted.</p>
      </Section>

      <Section title="9. Changes to Terms">
        <p>We may update these Terms at any time. Continued use of the Service after changes constitutes acceptance of the new Terms. We will notify you of material changes via email.</p>
      </Section>

      <Section title="10. Contact">
        <p>For questions about these Terms, contact us at <a href="mailto:legal@ledgerhaul.com" className="underline hover:text-foreground">legal@ledgerhaul.com</a>.</p>
      </Section>
    </main>

    <footer className="border-t border-border py-8 text-center text-xs text-muted-foreground">
      © {new Date().getFullYear()} LedgerHaul, Inc. ·{" "}
      <Link to="/privacy" className="hover:text-foreground underline">Privacy</Link> ·{" "}
      <Link to="/terms" className="hover:text-foreground underline">Terms</Link>
    </footer>
  </div>
);

export default Terms;
