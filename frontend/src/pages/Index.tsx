import { Navbar } from "@/components/landing/Navbar";
import { Hero } from "@/components/landing/Hero";
import { FactsBar } from "@/components/landing/FactsBar";
import { Settlements } from "@/components/landing/Settlements";
import { Features } from "@/components/landing/Features";
import { Compare } from "@/components/landing/Compare";
import { Pricing } from "@/components/landing/Pricing";
import { Testimonial } from "@/components/landing/Testimonial";
import { Closing } from "@/components/landing/Closing";

const Index = () => {
  return (
    <div className="landing min-h-[100dvh] antialiased">
      <Navbar />
      <main>
        <Hero />
        <FactsBar />
        <Settlements />
        <Features />
        <Compare />
        <Pricing />
        <Testimonial />
      </main>
      <Closing />
    </div>
  );
};

export default Index;
