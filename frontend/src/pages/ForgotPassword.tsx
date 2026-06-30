import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowRight, Loader2, CheckCircle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/users/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok || res.status === 404) {
        setSent(true);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.error || "Something went wrong. Please try again.");
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

        {sent ? (
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <CheckCircle size={48} style={{ color: "rgb(54,211,148)" }} />
            </div>
            <h1 className="text-2xl font-semibold text-white mb-3">Check your email</h1>
            <p className="text-muted-foreground mb-8">
              If <span className="text-white">{email}</span> is registered, you'll receive a password reset link shortly.
            </p>
            <Link to="/signin">
              <Button className="w-full h-11" variant="outline">Back to sign in</Button>
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-3xl font-semibold text-white mb-2">Forgot your password?</h1>
            <p className="text-muted-foreground mb-8">
              Enter your email and we'll send you a link to reset it.
            </p>

            {error && (
              <div className="mb-4 p-3 rounded-lg text-sm font-medium"
                style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "rgb(248,113,113)" }}>
                {error}
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
                    Send reset link
                    <ArrowRight className="ml-2 transition-transform group-hover:translate-x-1" size={16} />
                  </>
                )}
              </Button>
            </form>

            <p className="mt-8 text-center text-sm text-muted-foreground">
              Remember your password?{" "}
              <Link to="/signin" className="font-medium hover:underline" style={{ color: "rgb(54,211,148)" }}>
                Sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default ForgotPassword;
