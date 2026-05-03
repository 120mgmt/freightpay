const stack = [
  "PostgreSQL", "SQLAlchemy", "Alembic", "Flask-Migrate",
  "Stripe", "JWT", "Render", "Webhooks", "REST API",
];

export const Stack = () => {
  return (
    <section id="docs" className="relative py-16 border-y border-border bg-surface-muted/30">
      <div className="container mx-auto px-6">
        <p className="text-center text-xs uppercase tracking-[0.25em] text-muted-foreground mb-8">
          Built on a proven, production-grade stack
        </p>
        <div className="relative overflow-hidden mask-fade-radial">
          <div className="flex gap-12 animate-scroll-x w-max">
            {[...stack, ...stack, ...stack, ...stack].map((s, i) => (
              <div key={i} className="flex items-center gap-3 text-foreground/70 hover:text-primary transition-colors">
                <div className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: "rgb(54,211,148)", opacity: 0.7 }} />
                <span className="font-mono text-[15px] whitespace-nowrap">{s}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};