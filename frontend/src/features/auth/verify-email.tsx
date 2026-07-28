"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { verifyEmail } from "@/lib/api/auth";

type Status = "pending" | "verifying" | "verified" | "error";

export function VerifyEmail() {
  const search = useSearchParams();
  const token = search.get("token");
  const [status, setStatus] = useState<Status>("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || status !== "pending") return;
    setStatus("verifying");
    verifyEmail(token)
      .then(() => setStatus("verified"))
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : "This verification link is invalid or expired.");
        setStatus("error");
      });
  }, [token, status]);

  if (!token) {
    return (
      <div className="form-error" role="alert">
        This verification link is missing its token. Use the link from your email exactly as sent.
      </div>
    );
  }

  if (status === "pending" || status === "verifying") {
    return <div className="form-skeleton" />;
  }

  if (status === "verified") {
    return (
      <div className="success-state">
        <CheckCircle2 />
        <h2>Email verified</h2>
        <p>Your CreditFlow account is now active.</p>
        <Link className="primary-button" href="/login">
          Continue to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="form-error" role="alert">
      {error}
    </div>
  );
}
