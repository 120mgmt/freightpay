import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Copy, Check, ExternalLink } from "lucide-react";
import { useState } from "react";

const endpoints = [
  {
    method: "POST",
    path: "/v1/settlements/calculate",
    desc: "Calculate a contractor settlement for a given driver and period.",
    example: `{
  "driver_id": "drv_7834A",
  "period": "2025-W17",
  "loads": [
    { "miles": 1247, "rate": 0.62 },
    { "miles": 980, "rate": 0.58 }
  ],
  "deductions": ["fuel", "ifta"]
}`,
  },
  {
    method: "POST",
    path: "/users/login",
    desc: "Authenticate a user and receive a JWT token.",
    example: `{
  "email": "admin@company.com",
  "password": "your_password"
}`,
  },
  {
    method: "POST",
    path: "/users/register",
    desc: "Create a new user account and company.",
    example: `{
  "company_name": "Acme Freight",
  "email": "jane@acmefreight.com",
  "password": "secure_password",
  "first_name": "Jane",
  "last_name": "Doe"
}`,
  },
  {
    method: "GET",
    path: "/users/me",
    desc: "Get the authenticated user's profile. Requires Authorization header.",
    example: `curl -H "Authorization: Bearer lh_live_•••" \\
  https://api.ledgerhaul.com/users/me`,
  },
  {
    method: "POST",
    path: "/v1/payroll/run",
    desc: "Execute a payroll run for the given pay period.",
    example: `{
  "period": "2025-W17",
  "include_settlements": true,
  "payout_method": "stripe"
}`,
  },
  {
    method: "GET",
    path: "/v1/ledger/accounts",
    desc: "List all chart-of-account entries for the authenticated company.",
    example: `curl -H "Authorization: Bearer lh_live_•••" \\
  https://api.ledgerhaul.com/v1/ledger/accounts`,
  },
];

const CopyButton = ({ text }: { text: string }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={handleCopy} className="text-muted-foreground hover:text-white transition-colors" title="Copy">
      {copied ? <Check size={14} style={{ color: "rgb(54,211,148)" }} /> : <Copy size={14} />}
    </button>
  );
};

const methodColor = (method: string) => {
  if (method === "GET") return { bg: "rgba(96,165,250,0.1)", border: "rgba(96,165,250,0.3)", text: "rgb(96,165,250)" };
  if (method === "POST") return { bg: "rgba(54,211,148,0.1)", border: "rgba(54,211,148,0.3)", text: "rgb(54,211,148)" };
  return { bg: "rgba(253,224,71,0.1)", border: "rgba(253,224,71,0.3)", text: "rgb(253,224,71)" };
};

const ApiDocs = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header className="sticky top-0 z-50 h-[80px] flex items-center border-b border-border px-6"
        style={{ background: "rgba(8,13,17,0.85)", backdropFilter: "blur(24px)" }}>
        <Link to="/" className="flex items-center">
          <img src="/Logo.png" alt="LedgerHaul" className="h-14 w-auto" />
        </Link>
        <span className="ml-4 text-sm font-mono text-muted-foreground border-l border-border pl-4">
          API Reference
        </span>
        <div className="ml-auto">
          <Link to="/signin">
            <Button size="sm" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 10, fontWeight: 500, fontSize: 14 }}>
              Get API Key
            </Button>
          </Link>
        </div>
      </header>

      <div className="container mx-auto px-6 py-16 max-w-4xl">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors mb-8">
          <ArrowLeft size={16} />
          Back to home
        </Link>

        <div className="mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-5 text-xs font-mono"
            style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" }}>
            <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
            v3.1
          </div>
          <h1 className="text-4xl sm:text-5xl font-semibold text-white mb-4 tracking-tight">
            API Reference
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl">
            Integrate LedgerHaul's payroll, settlements, and bookkeeping APIs into your
            trucking operations. All endpoints require authentication via Bearer token.
          </p>
        </div>

        {/* Base URL */}
        <div className="rounded-xl border border-border p-5 mb-10" style={{ background: "rgba(19,27,37,0.6)" }}>
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Base URL</div>
          <div className="flex items-center gap-3">
            <code className="font-mono text-white text-sm">https://api.ledgerhaul.com</code>
            <CopyButton text="https://api.ledgerhaul.com" />
          </div>
        </div>

        {/* Auth section */}
        <div className="rounded-xl border border-border p-5 mb-10" style={{ background: "rgba(19,27,37,0.6)" }}>
          <h2 className="text-lg font-semibold text-white mb-3">Authentication</h2>
          <p className="text-sm text-muted-foreground mb-4">
            All API requests must include a Bearer token in the Authorization header:
          </p>
          <div className="rounded-lg border border-border p-4 font-mono text-sm bg-surface-muted/40 flex items-center justify-between">
            <code className="text-foreground/90">Authorization: Bearer lh_live_your_api_key</code>
            <CopyButton text="Authorization: Bearer lh_live_your_api_key" />
          </div>
        </div>

        {/* Endpoints */}
        <h2 className="text-xl font-semibold text-white mb-6">Endpoints</h2>
        <div className="space-y-6">
          {endpoints.map((ep) => {
            const mc = methodColor(ep.method);
            return (
              <div key={ep.path} className="rounded-xl border border-border overflow-hidden"
                style={{ background: "rgba(19,27,37,0.6)" }}>
                <div className="px-5 py-4 border-b border-border flex items-center gap-3">
                  <span className="px-2.5 py-1 rounded-md text-xs font-bold font-mono"
                    style={{ background: mc.bg, border: `1px solid ${mc.border}`, color: mc.text }}>
                    {ep.method}
                  </span>
                  <code className="text-white font-mono text-sm">{ep.path}</code>
                </div>
                <div className="px-5 py-4">
                  <p className="text-sm text-muted-foreground mb-4">{ep.desc}</p>
                  <div className="rounded-lg border border-border bg-surface-muted/40 overflow-hidden">
                    <div className="px-4 py-2 border-b border-border flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-mono">Example</span>
                      <CopyButton text={ep.example} />
                    </div>
                    <pre className="p-4 text-sm font-mono text-foreground/90 overflow-x-auto whitespace-pre-wrap">
                      {ep.example}
                    </pre>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* CTA */}
        <div className="mt-16 text-center rounded-2xl border p-10"
          style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(19,27,37,0.6)" }}>
          <h3 className="text-2xl font-semibold text-white mb-3">Ready to integrate?</h3>
          <p className="text-muted-foreground mb-6">
            Create an account to get your API keys and start building.
          </p>
          <Link to="/register">
            <Button
              size="lg"
              className="text-[15px] font-semibold px-8"
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 30px rgba(54,211,148,0.3)" }}
            >
              Get started free
              <ExternalLink className="ml-2" size={16} />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default ApiDocs;
