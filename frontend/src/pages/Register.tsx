import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowRight, Eye, EyeOff, Loader2, CheckCircle2 } from "lucide-react";

const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    company_name: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const update = (field: string, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    const result = await register(form);
    setLoading(false);

    if (result.success) {
      setSuccess(true);
    } else {
      setError(result.error || "Registration failed.");
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-6">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center"
            style={{ background: "rgba(54,211,148,0.15)", border: "1px solid rgba(54,211,148,0.4)" }}>
            <CheckCircle2 size={32} style={{ color: "rgb(54,211,148)" }} />
          </div>
          <h1 className="text-3xl font-semibold text-white mb-3">Account created!</h1>
          <p className="text-muted-foreground mb-8">
            Please check your email to verify your account, then sign in to get started.
          </p>
          <Button
            onClick={() => navigate("/signin")}
            className="h-11 px-8 text-[15px] font-semibold"
            style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 30px rgba(54,211,148,0.3)" }}
          >
            Go to Sign In
            <ArrowRight className="ml-2" size={16} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      {/* Left — decorative panel */}
      <div className="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden"
        style={{ background: "rgb(14,20,27)" }}>
        <div className="absolute inset-0 grid-bg opacity-20 mask-fade-radial" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] rounded-full blur-[100px]"
          style={{ background: "rgba(54,211,148,0.15)" }} />
        <div className="relative text-center px-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-6 text-xs font-mono"
            style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" }}>
            <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
            14-DAY FREE TRIAL
          </div>
          <h2 className="text-3xl font-semibold text-white mb-4">
            Get started in<br />under 5 minutes.
          </h2>
          <p className="text-muted-foreground max-w-sm mx-auto">
            No credit card required. Full API access from day one. Cancel anytime.
          </p>
        </div>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          <Link to="/" className="inline-block mb-10">
            <img src="/Logo.png" alt="LedgerHaul" className="h-20 w-auto" />
          </Link>

          <h1 className="text-3xl font-semibold text-white mb-2">Create your account</h1>
          <p className="text-muted-foreground mb-8">
            Start your 14-day free trial. No credit card required.
          </p>

          {error && (
            <div className="mb-6 p-3 rounded-lg text-sm font-medium"
              style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="first_name" className="text-sm text-foreground/80">First name</Label>
                <Input
                  id="first_name"
                  placeholder="Jane"
                  value={form.first_name}
                  onChange={(e) => update("first_name", e.target.value)}
                  required
                  className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name" className="text-sm text-foreground/80">Last name</Label>
                <Input
                  id="last_name"
                  placeholder="Doe"
                  value={form.last_name}
                  onChange={(e) => update("last_name", e.target.value)}
                  required
                  className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="company_name" className="text-sm text-foreground/80">Company name</Label>
              <Input
                id="company_name"
                placeholder="Acme Freight LLC"
                value={form.company_name}
                onChange={(e) => update("company_name", e.target.value)}
                required
                className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm text-foreground/80">Work email</Label>
              <Input
                id="email"
                type="email"
                placeholder="jane@acmefreight.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                required
                className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm text-foreground/80">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Min. 8 characters"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                  required
                  minLength={8}
                  className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 text-[15px] font-semibold group mt-2"
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 30px rgba(54,211,148,0.3)" }}
            >
              {loading ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <>
                  Create account
                  <ArrowRight className="ml-2 transition-transform group-hover:translate-x-1" size={16} />
                </>
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/signin" className="font-medium hover:underline" style={{ color: "rgb(54,211,148)" }}>
              Sign in
            </Link>
          </p>

          <p className="mt-4 text-center text-xs text-muted-foreground/60">
            By creating an account you agree to our{" "}
            <Link to="/terms" className="underline hover:text-muted-foreground">Terms of Service</Link>
            {" "}and{" "}
            <Link to="/privacy" className="underline hover:text-muted-foreground">Privacy Policy</Link>.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
