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
            <Loader2 className="mx-auto mb-6 animate-spin" size={48} style={{ color: "rgb(54,211,148)" }} />
            <h1 className="text-2xl font-semibold text-white">Verifying your email…</h1>
          </>
        )}
        {status === "success" && (
          <>
            <div
              className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center"
              style={{ background: "rgba(54,211,148,0.15)", border: "1px solid rgba(54,211,148,0.4)" }}
            >
              <CheckCircle2 size={32} style={{ color: "rgb(54,211,148)" }} />
            </div>
            <h1 className="text-3xl font-semibold text-white mb-3">Email verified!</h1>
            <p className="text-muted-foreground mb-8">
              Your account is now active. Sign in to get started.
            </p>
            <Button
              asChild
              className="h-11 px-8 text-[15px] font-semibold"
              style={{
                background: "rgb(54,211,148)",
                color: "rgb(14,20,27)",
                borderRadius: 12,
                boxShadow: "0 0 30px rgba(54,211,148,0.3)",
              }}
            >
              <Link to="/signin">Sign in →</Link>
            </Button>
          </>
        )}
        {status === "error" && (
          <>
            <div
              className="mx-auto mb-6 h-16 w-16 rounded-full flex items-center justify-center"
              style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)" }}
            >
              <XCircle size={32} style={{ color: "rgb(248,113,113)" }} />
            </div>
            <h1 className="text-3xl font-semibold text-white mb-3">Verification failed</h1>
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
