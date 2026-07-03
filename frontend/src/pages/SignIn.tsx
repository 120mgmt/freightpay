import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowRight, Eye, EyeOff, Loader2 } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";

const SignIn = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [errorCode, setErrorCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMsg, setResendMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setErrorCode("");
    setResendMsg("");
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);
    if (result.success) {
      const redirect = sessionStorage.getItem("lh_redirect") || "/dashboard";
      sessionStorage.removeItem("lh_redirect");
      navigate(redirect);
    } else {
      setError(result.error || "Login failed.");
      setErrorCode(result.code || "");
    }
  };

  const handleResend = async () => {
    setResendLoading(true);
    setResendMsg("");
    try {
      const res = await fetch(`${API_BASE}/verify/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) {
        setResendMsg("Verification email sent — check your inbox.");
      } else {
        setResendMsg(data.error === "user_not_found" ? "No account found with that email." : "Could not resend — try again.");
      }
    } catch {
      setResendMsg("Network error. Please try again.");
    }
    setResendLoading(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      {/* Left — form */}
      <div className="flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">
          <Link to="/" className="inline-block mb-8">
            <img src="/logo-light.png" alt="LedgerHaul" className="h-14 w-auto" />
          </Link>

          <h1 className="text-3xl font-extrabold tracking-tight mb-2">Welcome back</h1>
          <p className="text-muted-foreground mb-8">
            Sign in to your LedgerHaul account to continue.
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg text-sm font-medium border border-destructive/30 bg-destructive/5 text-destructive">
              {error}
            </div>
          )}

          {errorCode === "EMAIL_NOT_VERIFIED" && (
            <div className="mb-6 text-sm text-center">
              {resendMsg ? (
                <p className="text-primary">{resendMsg}</p>
              ) : (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendLoading}
                  className="text-primary hover:underline"
                >
                  {resendLoading ? "Sending…" : "Resend verification email"}
                </button>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 bg-surface"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm">Password</Label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
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

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 text-[15px] font-semibold group rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <>
                  Sign in
                  <ArrowRight className="ml-2 transition-transform group-hover:translate-x-1" size={16} />
                </>
              )}
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Don't have an account?{" "}
            <Link to="/register" className="font-medium text-primary hover:underline">
              Create one free
            </Link>
          </p>

          <p className="mt-4 text-center text-xs text-muted-foreground/70">
            By signing in you agree to our{" "}
            <Link to="/terms" className="underline hover:text-muted-foreground">Terms of Service</Link>
            {" "}and{" "}
            <Link to="/privacy" className="underline hover:text-muted-foreground">Privacy Policy</Link>.
          </p>
        </div>
      </div>

      {/* Right — brand panel */}
      <div className="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden bg-surface-muted border-l border-border">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] rounded-full blur-[100px] bg-[hsl(var(--primary-glow)/0.15)]" />
        <div className="relative text-center px-12">
          <img src="/logo-light.png" alt="" className="h-24 w-auto mx-auto mb-8" />
          <h2 className="text-3xl font-extrabold tracking-tight mb-4">
            Financial clarity<br />for every mile.
          </h2>
          <p className="text-muted-foreground max-w-sm mx-auto">
            Payroll, settlements, and bookkeeping — unified in one platform built for trucking operations.
          </p>
        </div>
      </div>
    </div>
  );
};

export default SignIn;
