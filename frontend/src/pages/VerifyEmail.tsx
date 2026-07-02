import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_BASE = import.meta.env.VITE_API_URL || "";

const VerifyEmail = () => {
  const [params] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("No verification token found in this link.");
      return;
    }
    fetch(`${API_BASE}/verify/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "email_verified" || data.status === "already_verified") {
          setStatus("success");
        } else {
          setStatus("error");
          setMessage(
            data.error === "token_expired"
              ? "This link has expired. Please request a new one from the sign-in page."
              : "Invalid or already-used verification link."
          );
        }
      })
      .catch(() => {
        setStatus("error");
        setMessage("Network error. Please try again.");
      });
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-6">
      <div className="w-full max-w-md text-center">
        {status === "loading" && (
          <>
            <Loader2 className="mx-auto mb-6 animate-spin text-primary" size={48} />
            <h1 className="text-2xl font-extrabold tracking-tight">Verifying your email…</h1>
          </>
        )}
        {status === "success" && (
          <>
            <div
              className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center bg-primary/10 border border-primary/30"
            >
              <CheckCircle2 size={32} className="text-primary" />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight mb-3">Email verified!</h1>
            <p className="text-muted-foreground mb-8">
              Your account is now active. Sign in to get started.
            </p>
            <Button
              asChild
              className="h-11 px-8 text-[15px] font-semibold rounded-full bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]"
            >
              <Link to="/signin">Sign in →</Link>
            </Button>
          </>
        )}
        {status === "error" && (
          <>
            <div
              className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center bg-destructive/5 border border-destructive/30"
            >
              <XCircle size={32} className="text-destructive" />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight mb-3">Verification failed</h1>
            <p className="text-muted-foreground mb-8">{message}</p>
            <Button asChild variant="outline" className="h-11 px-8">
              <Link to="/signin">Back to sign in</Link>
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

export default VerifyEmail;
