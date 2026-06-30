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
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          {/* Logo */}
          <Link to="/" className="inline-block mb-10">
            <img src="/Logo.png" alt="LedgerHaul" className="h-20 w-auto" />
          </Link>

          <h1 className="text-3xl font-semibold text-white mb-2">Welcome back</h1>
          <p className="text-muted-foreground mb-8">
            Sign in to your LedgerHaul account to continue.
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg text-sm font-medium"
              style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
              {error}
            </div>
          )}

          {errorCode === "EMAIL_NOT_VERIFIED" && (
            <div className="mb-6 text-sm text-center">
              {resendMsg ? (
                <p style={{ color: "rgb(54,211,148)" }}>{resendMsg}</p>
              ) : (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendLoading}
                  className="hover:underline"
                  style={{ color: "rgb(54,211,148)" }}
                >
                  {resendLoading ? "Sending…" : "Resend verification email"}
                </button>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm text-foreground/80">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm text-foreground/80">Password</Label>
                <Link to="/forgot-password" className="text-xs hover:underline" style={{ color: "rgb(54,211,148)" }}>
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
              className="w-full h-11 text-[15px] font-semibold group"
              style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 30px rgba(54,211,148,0.3)" }}
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
            <Link to="/register" className="font-medium hover:underline" style={{ color: "rgb(54,211,148)" }}>
              Create one free
            </Link>
          </p>
        </div>
      </div>

      {/* Right — decorative panel */}
      <div className="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden"
        style={{ background: "rgb(14,20,27)" }}>
        <div className="absolute inset-0 grid-bg opacity-20 mask-fade-radial" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] rounded-full blur-[100px]"
          style={{ background: "rgba(54,211,148,0.15)" }} />
        <div className="relative text-center px-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-6 text-xs font-mono"
            style={{ borderColor: "rgba(54,211,148,0.3)", background: "rgba(54,211,148,0.1)", color: "rgb(54,211,148)" }}>
            <span className="h-1.5 w-1.5 rounded-full animate-pulse-dot" style={{ background: "rgb(54,211,148)" }} />
            SECURE ACCESS
          </div>
          <h2 className="text-3xl font-semibold text-white mb-4">
            Financial clarity<br />for every mile.
          </h2>
          <p className="text-muted-foreground max-w-sm mx-auto">
            Payroll, settlements, bookkeeping — unified in one production-grade backend for trucking operations.
          </p>
        </div>
      </div>
    </div>
  );
};

export default SignIn;
