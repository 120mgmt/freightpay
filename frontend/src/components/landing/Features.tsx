import { Banknote, FileCheck, History } from "lucide-react";
import { Reveal } from "./Reveal";
import { IMAGES } from "./images";

const smallCells = [
  {
    icon: Banknote,
    title: "Direct deposit Fridays",
    body: "Payouts land on schedule through Stripe, with payout status visible on every statement.",
  },
  {
    icon: FileCheck,
    title: "Year-end in one click",
    body: "1099-NEC forms generate from the same records you ran payroll on all year.",
  },
  {
    icon: History,
    title: "Every change, on the record",
    body: "An immutable audit trail backs every settlement, edit, and payout you make.",
  },
];

export const Features = () => (
  <section id="features" className="py-24 lg:py-32 bg-surface border-y border-border">
    <div className="max-w-7xl mx-auto px-6">
      <Reveal>
        <h2 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold tracking-tighter leading-[1.08] max-w-2xl">
          The back office, handled.
        </h2>
        <p className="mt-5 text-lg text-muted-foreground leading-relaxed max-w-[36rem]">
          Pay runs, books, taxes, and records work off one system, so nothing
          gets re-keyed and nothing falls through.
        </p>
      </Reveal>

      <div className="mt-12 grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Driver portal photo cell */}
        <Reveal className="lg:col-span-7">
          <div className="relative h-full min-h-[320px] rounded-2xl overflow-hidden">
            <img
              src={IMAGES.driverCab}
              alt="Truck driver checking his settlement on his phone from the cab"
              className="absolute inset-0 h-full w-full object-cover"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[hsl(192_30%_8%/0.85)] via-[hsl(192_30%_8%/0.25)] to-transparent" />
            <div className="absolute bottom-0 p-7 sm:p-8">
              <h3 className="text-white text-xl font-bold">Drivers see every line</h3>
              <p className="mt-2 text-white/85 text-[15px] leading-relaxed max-w-md">
                Statements open from the cab, itemized to the load, with pay
                history a tap away.
              </p>
            </div>
          </div>
        </Reveal>

        {/* Bookkeeping cell */}
        <Reveal className="lg:col-span-5" delay={100}>
          <div className="h-full min-h-[320px] rounded-2xl bg-gradient-to-br from-[hsl(161_62%_26%)] to-[hsl(170_55%_16%)] p-7 sm:p-8 flex flex-col justify-end">
            <h3 className="text-white text-xl font-bold">Books that close themselves</h3>
            <p className="mt-2 text-white/85 text-[15px] leading-relaxed">
              Every settlement posts balanced double-entry ledger lines the
              moment it runs. P&L, balance sheet, and cash flow stay current,
              and your accountant gets a QuickBooks export whenever they ask.
            </p>
          </div>
        </Reveal>

        {/* Three fact cells */}
        {smallCells.map((c, i) => (
          <Reveal key={c.title} className="lg:col-span-4" delay={i * 80}>
            <div className="h-full rounded-2xl border border-border bg-card p-7">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[hsl(var(--primary)/0.1)]">
                <c.icon size={19} strokeWidth={2} className="text-primary" />
              </span>
              <h3 className="mt-4 text-lg font-bold">{c.title}</h3>
              <p className="mt-2 text-[15px] text-muted-foreground leading-relaxed">{c.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);
