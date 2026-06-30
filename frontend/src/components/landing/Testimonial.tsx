import { Reveal } from "./Reveal";
import { IMAGES } from "./images";

/* Sample testimonial; replace with a real customer quote before launch. */
export const Testimonial = () => (
  <section className="py-24 lg:py-32">
    <div className="max-w-6xl mx-auto px-6">
      <div className="grid lg:grid-cols-12 gap-10 lg:gap-16 items-center">
        <Reveal className="lg:col-span-4">
          <img
            src={IMAGES.fleetOwner}
            alt="Fleet owner standing in her truck yard at dusk"
            className="w-full rounded-2xl object-cover aspect-[3/4] max-w-sm mx-auto lg:mx-0"
            loading="lazy"
          />
        </Reveal>
        <Reveal className="lg:col-span-8" delay={120}>
          <blockquote className="text-2xl sm:text-3xl lg:text-[2.1rem] font-bold tracking-tight leading-snug">
            {"“"}We ran nine trucks out of spreadsheets for years. Now
            settlements go out Friday morning and the books are already done.
            {"”"}
          </blockquote>
          <p className="mt-6 text-[15px]">
            <span className="font-semibold">Marcy Hutto</span>
            <span className="text-muted-foreground">
              , Owner, Hutto Freight Lines (Amarillo, TX)
            </span>
          </p>
        </Reveal>
      </div>
    </div>
  </section>
);
