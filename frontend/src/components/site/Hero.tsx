import { Button } from "@/components/ui/button";
import { ArrowRight, Terminal } from "lucide-react";

export const Hero = () => {
  return (
    <section className="relative pt-32 pb-24 overflow-hidden">
      {/* Backgrounds */}
      <div className="absolute inset-0 bg-mesh" />
      <div className="absolute inset-0 grid-bg mask-fade-radial opacity-40" />
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-primary/10 blur-[120px] rounded-full" />

      <div className="container relative mx-auto px-6">
        {/* Status pill */}
        <div className="flex justify-center mb-8 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 backdrop-blur px-4 py-1.5 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-pulse-dot absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
            </span>
            <span className="text-muted-foreground">All systems operational</span>
            <span className="text-border">·</span>
            <span className="text-primary font-mono">v3.1 live</span>
          </div>
        </div>

        {/* Headline */}
        <div className="max-w-5xl mx-auto text-center animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tight leading-[1.05] text-white">
            The production backend
            <br />
            for{" "}
            <span style={{ color: "rgb(54,211,148)" }}>trucking finance</span>.
          </h1>
          <p className="mt-7 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            Programmable payroll, contractor settlements, double-entry bookkeeping,
            and Stripe subscription billing — engineered as one API-first service.
          </p>

          {/* CTAs */}
          <div className="mt-10 flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              size="lg"
              className="group text-[15px] font-semibold px-8 py-3 h-auto"
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 40px rgba(54,211,148,0.35)" }}
            >
              Start free trial
              <ArrowRight className="ml-2 transition-transform group-hover:translate-x-1" size={16} />
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="group text-[15px] font-medium px-8 py-3 h-auto border-border bg-transparent text-muted-foreground hover:text-foreground"
              style={{ borderRadius: 12 }}
            >
              <Terminal size={15} className="mr-2" />
              View API docs
            </Button>
          </div>

          <p className="mt-6 text-xs text-muted-foreground font-mono">
            $ curl ledgerhaul.io/quickstart &nbsp;·&nbsp; Production-ready in &lt;5 minutes
          </p>
        </div>

        {/* API Terminal mockup */}
        <div className="mt-20 max-w-5xl mx-auto animate-fade-in-up" style={{ animationDelay: "0.25s" }}>
          <div className="relative rounded-2xl border border-border bg-surface/80 backdrop-blur-xl overflow-hidden"
            style={{ boxShadow: "0 30px 80px -20px rgba(54,211,148,0.25), 0 0 0 1px rgb(33,42,54)" }}>

            {/* Title bar */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface-muted">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-destructive/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-primary/60" />
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse-dot" />
                api.ledgerhaul.com — settlements.run
              </div>
              <div className="font-mono text-xs" style={{ color: "rgb(54,211,148)" }}>200 OK</div>
            </div>

            {/* Two-column request/response */}
            <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border font-mono text-sm">
              {/* REQUEST */}
              <div className="p-6">
                <div className="text-xs text-muted-foreground mb-3">REQUEST</div>
                <pre className="text-foreground/90 leading-relaxed text-[13px] whitespace-pre-wrap">
<span style={{ color: "rgb(54,211,148)" }}>POST</span> /v1/settlements/calculate{"\n"}
<span className="text-muted-foreground">Authorization:</span> Bearer lh_live_•••{"\n\n"}
{"{\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"driver_id"</span>: <span style={{ color: "rgb(253,224,71,0.9)" }}>"drv_7834A"</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"period"</span>: <span style={{ color: "rgb(253,224,71,0.9)" }}>"2025-W17"</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"loads"</span>: [{"\n"}
    {"{"} <span style={{ color: "rgb(54,211,148)" }}>"miles"</span>: 1247, <span style={{ color: "rgb(54,211,148)" }}>"rate"</span>: 0.62 {"}"},{"\n"}
    {"{"} <span style={{ color: "rgb(54,211,148)" }}>"miles"</span>: 980, <span style={{ color: "rgb(54,211,148)" }}>"rate"</span>: 0.58 {"}"}{"\n"}
  ],{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"deductions"</span>: [<span style={{ color: "rgb(253,224,71,0.9)" }}>"fuel"</span>, <span style={{ color: "rgb(253,224,71,0.9)" }}>"ifta"</span>]{"\n"}
{"}"}
                </pre>
              </div>

              {/* RESPONSE */}
              <div className="p-6 bg-surface-muted/40">
                <div className="text-xs text-muted-foreground mb-3 flex items-center justify-between">
                  <span>RESPONSE</span>
                  <span style={{ color: "rgb(54,211,148)" }}>42ms</span>
                </div>
                <pre className="text-foreground/90 leading-relaxed text-[13px] whitespace-pre-wrap">
{"{\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"settlement_id"</span>: <span style={{ color: "rgb(253,224,71,0.9)" }}>"set_b9f3d2"</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"gross_pay"</span>: <span style={{ color: "rgb(54,211,148)" }}>1341.54</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"deductions"</span>: <span style={{ color: "rgb(54,211,148)" }}>182.30</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"net_pay"</span>: <span style={{ color: "rgb(54,211,148)" }}>1159.24</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"ledger_entries"</span>: 6,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"stripe_payout_id"</span>:{"\n"}
    <span style={{ color: "rgb(253,224,71,0.9)" }}>"po_1Q8xM2..."</span>,{"\n"}
  <span style={{ color: "rgb(54,211,148)" }}>"status"</span>: <span style={{ color: "rgb(253,224,71,0.9)" }}>"posted"</span>{"\n"}
{"}"}
                </pre>
              </div>
            </div>
          </div>

          {/* Trusted by strip */}
          <div className="mt-16 text-center">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground mb-6">
              Trusted by carriers moving $1M+ bills weekly
            </p>
            <div className="flex flex-wrap justify-center items-center gap-x-10 gap-y-4 opacity-60">
              {["NORTHBOUND", "PACIFIC HAUL", "RIDGELINE", "MERIDIAN FREIGHT", "CASCADE LOG.", "IRONROAD"].map((b) => (
                <span key={b} className="font-semibold tracking-widest text-foreground/70 text-sm">{b}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};