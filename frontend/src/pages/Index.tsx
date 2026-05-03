import { Navbar } from "@/components/site/Navbar";
import { Hero } from "@/components/site/Hero";
import { Stack } from "@/components/site/Stack";
import { Features } from "@/components/site/Features";
import { Capabilities } from "@/components/site/Capabilities";
import { Pricing } from "@/components/site/Pricing";
import { CTA } from "@/components/site/CTA";
import { Footer } from "@/components/site/Footer";

const Index = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main>
        <Hero />
        <Stack />
        <Features />
        <Capabilities />
        <Pricing />
        <CTA />
      </main>
      <Footer />
    </div>
  );
};

export default Index;
