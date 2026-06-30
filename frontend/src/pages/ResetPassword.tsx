import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowRight, Eye, EyeOff, Loader2, CheckCircle, XCircle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";

const ResetPassword = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  if (!token) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-6">
        <div className="w-full max-w-md text-center">
          <XCircle size={48} className="mx-auto mb-4" style={{ color: "rgb(248,113,113)" }} />
          <h1 className="text-2xl font-semibold text-white mb-3">Invalid link</h1>
          <p className="text-muted-foreground mb-8">This password reset link is missing a token. Please request a new one.</p>
          <Link to="/forgot-password">
            <Button className="w-full h-11" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
              Request new link
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("Passwords do not match."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/users/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      if (res.ok) {
        setDone(true);
        setTimeout(() => navigate("/signin"), 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.error || "Reset failed. The link may have expired.");
      }
    } catch {
      setError("Network error. Please try again.");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <Link to="/" className="inline-block mb-10">
          <img src="/Logo.png" alt="LedgerHaul" className="h-20 w-auto" />
        </Link>

        {done ? (
          <div className="text-center">
            <CheckCircle size={48} className="mx-auto mb-4" style={{ color: "rgb(54,211,148)" }} />
            <h1 className="text-2xl font-semibold text-white mb-3">Password updated</h1>
            <p className="text-muted-foreground mb-8">Your password has been reset. Redirecting to sign in…</p>
            <Link to="/signin">
              <Button className="w-full h-11" style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)" }}>
                Sign in now
              </Button>
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-3xl font-semibold text-white mb-2">Set new password</h1>
            <p className="text-muted-foreground mb-8">Choose a strong password for your account.</p>

            {error && (
              <div className="mb-4 p-3 rounded-lg text-sm font-medium"
                style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm text-foreground/80">New password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPw ? "text" : "password"}
                    placeholder="Min. 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50 pr-10"
                  />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm" className="text-sm text-foreground/80">Confirm password</Label>
                <Input
                  id="confirm"
                  type={showPw ? "text" : "password"}
                  placeholder="Re-enter password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  className="h-11 bg-surface border-border text-white placeholder:text-muted-foreground/50 focus-visible:ring-primary/50"
                />
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 text-[15px] font-semibold group"
                style={{ background: "rgb(54,211,148)", color: "rgb(14,20,27)", borderRadius: 12, boxShadow: "0 0 30px rgba(54,211,148,0.3)" }}
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : (
                  <>Reset password <ArrowRight className="ml-2 group-hover:translate-x-1 transition-transform" size={16} /></>
                )}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

export default ResetPassword;
