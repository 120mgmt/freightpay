import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { IMAGES } from "./images";

export const Hero = () => {
  const navigate = useNavigate();

  return (
    <section className="relative pt-20">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-12 gap-10 lg:gap-14 items-center pt-12 lg:pt-20 pb-16 lg:pb-24">
          {/* Copy */}
          <div className="lg:col-span-6 animate-fade-in-up">
            <h1 className="text-4xl sm:text-5xl lg:text-[2.9rem] xl:text-[3.5rem] font-extrabold tracking-tighter leading-[1.05] [text-wrap:balance]">
              Payroll that knows what a mile is worth.
            </h1>
            <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-[32rem]">
              Driver settlements, contractor pay, and clean books in one place.
              Built for American carriers, not adapted for them.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <button
                onClick={() => navigate("/register")}
                className="group inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground text-[15px] font-semibold px-7 py-3.5 hover:bg-[hsl(var(--primary-dim))] active:scale-[0.98] transition-all"
              >
                Start free trial
                <ArrowRight
                  size={16}
                  strokeWidth={2}
                  className="transition-transform group-hover:translate-x-0.5"
                />
              </button>
              <button
                onClick={() =>
                  document.querySelector("#how-it-works")?.scrollIntoView({ behavior: "smooth" })
                }
                className="rounded-full border border-border bg-surface text-foreground text-[15px] font-semibold px-7 py-3.5 hover:border-[hsl(var(--muted-foreground)/0.5)] active:scale-[0.98] transition-all"
              >
                See how it works
              </button>
            </div>
          </div>

          {/* Photo */}
          <div
            className="lg:col-span-6 animate-fade-in-up"
            style={{ animationDelay: "0.15s" }}
          >
            <div className="relative">
              <div className="absolute -inset-4 lg:-inset-6 rounded-2xl bg-[hsl(var(--primary)/0.07)] -rotate-1" />
              <img
                src={IMAGES.heroTruck}
                alt="Semi truck hauling a trailer on an open US interstate at sunset"
                className="relative w-full rounded-2xl object-cover aspect-[4/3] shadow-[0_24px_60px_-24px_hsl(200_35%_11%/0.35)]"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
