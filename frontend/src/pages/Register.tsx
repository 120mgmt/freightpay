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
  const [agree, setAgree] = useState(false);
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
    if (!agree) {
      setError("Please accept the Terms of Service and Privacy Policy.");
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
          <img src="/logo-light.png" alt="LedgerHaul" className="h-20 w-auto mx-auto mb-6" />
          <div className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center bg-primary/10 border border-primary/30">
            <CheckCircle2 size={32} className="text-primary" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight mb-3">Account created!</h1>
          <p className="text-muted-foreground mb-8">
            Please check your email to verify your account, then sign in to get started.
          </p>
          <Button
            onClick={() => navigate("/signin")}
            className="h-11 px-8 text-[15px] font-semibold rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]"
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
      {/* Left — dark brand panel */}
      <div className="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden bg-[hsl(var(--ink))]">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] rounded-full blur-[100px] bg-[hsl(var(--primary-glow)/0.2)]" />
        <div className="relative text-center px-12">
          <img src="/Logo.png" alt="" className="h-28 w-auto mx-auto mb-8" />
          <h2 className="text-3xl font-extrabold tracking-tight text-white mb-4">
            Get started in<br />under 5 minutes.
          </h2>
          <p className="text-white/60 max-w-sm mx-auto">
            14-day free trial. No credit card required. Cancel anytime.
          </p>
        </div>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">
          <Link to="/" className="inline-block mb-8">
            <img src="/logo-light.png" alt="LedgerHaul" className="h-24 w-auto -ml-2" />
          </Link>

          <h1 className="text-3xl font-extrabold tracking-tight mb-2">Create your account</h1>
          <p className="text-muted-foreground mb-8">
            Start your 14-day free trial. No credit card required.
          </p>

          {error && (
            <div className="mb-6 p-3 rounded-lg text-sm font-medium border border-destructive/30 bg-destructive/5 text-destructive">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="first_name" className="text-sm">First name</Label>
                <Input
                  id="first_name"
                  placeholder="Jane"
                  value={form.first_name}
                  onChange={(e) => update("first_name", e.target.value)}
                  required
                  className="h-11 bg-surface"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name" className="text-sm">Last name</Label>
                <Input
                  id="last_name"
                  placeholder="Doe"
                  value={form.last_name}
                  onChange={(e) => update("last_name", e.target.value)}
                  required
                  className="h-11 bg-surface"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="company_name" className="text-sm">Company name</Label>
              <Input
                id="company_name"
                placeholder="Acme Freight LLC"
                value={form.company_name}
                onChange={(e) => update("company_name", e.target.value)}
                required
                className="h-11 bg-surface"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm">Work email</Label>
              <Input
                id="email"
                type="email"
                placeholder="jane@acmefreight.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                required
                className="h-11 bg-surface"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Min. 8 characters"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                  required
                  minLength={8}
                  className="h-11 bg-surface pr-10"
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

            <label className="flex items-start gap-2.5 text-sm text-muted-foreground cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={agree}
                onChange={(e) => setAgree(e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-[hsl(var(--primary))]"
              />
              <span>
                I agree to the{" "}
                <Link to="/terms" className="text-primary underline">Terms of Service</Link>
                {" "}and{" "}
                <Link to="/privacy" className="text-primary underline">Privacy Policy</Link>.
              </span>
            </label>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 text-[15px] font-semibold group mt-2 rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]"
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
            <Link to="/signin" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
