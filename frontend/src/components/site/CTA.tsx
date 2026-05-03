import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export const CTA = () => {
  const navigate = useNavigate();

  return (
    <section className="relative py-32 overflow-hidden">
      <div className="container mx-auto px-6">
        <div className="relative max-w-5xl mx-auto rounded-3xl border p-12 md:p-20 text-center overflow-hidden"
          style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgb(19,27,37)" }}>

          <div className="absolute inset-0 bg-mesh opacity-80" />
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full blur-[100px]"
            style={{ background: "rgba(54,211,148,0.2)" }} />
          <div className="absolute inset-0 grid-bg opacity-20 mask-fade-radial" />

          <div className="relative">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-white mb-6 max-w-3xl mx-auto leading-tight">
              Ship the backend. Run the freight.
            </h2>
            <p className="text-lg text-muted-foreground max-w-xl mx-auto mb-10">
              Deploy LedgerHaul in an afternoon. Calculate your first settlement
              before your next dispatch window closes.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                size="lg"
                className="group text-[15px] font-semibold px-8 py-3 h-auto"
                style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 40px rgba(54,211,148,0.35)" }}
                onClick={() => navigate("/register")}
              >
                Start free trial
                <ArrowRight className="ml-2 transition-transform group-hover:translate-x-1" size={16} />
              </Button>
              <Button
                size="lg"
                className="text-[15px] font-medium px-8 py-3 h-auto border-border bg-transparent text-muted-foreground hover:text-foreground"
                variant="outline"
                style={{ borderRadius: 12 }}
                onClick={() => window.location.href = "mailto:engineering@ledgerhaul.com"}
              >
                Talk to engineering
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};