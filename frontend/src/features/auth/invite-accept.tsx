"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { acceptInvite } from "@/lib/api/tenants";

type Status = "pending" | "accepting" | "accepted" | "error";

export function InviteAccept() {
  const search = useSearchParams();
  const router = useRouter();
  const { user, ready } = useAuth();
  const token = search.get("token");
  const [status, setStatus] = useState<Status>("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !token || !user || status !== "pending") return;
    setStatus("accepting");
    acceptInvite(token)
      .then(() => setStatus("accepted"))
      .catch((reason) => {
        setError((reason as Error).message);
        setStatus("error");
      });
  }, [ready, token, user, status]);

  if (!token) {
    return (
      <div className="form-error" role="alert">
        This invite link is missing its token. Ask whoever invited you to resend it.
      </div>
    );
  }

  if (!ready || status === "accepting") {
    return <div className="form-skeleton" />;
  }

  if (status === "accepted") {
    return (
      <div className="success-state">
        <CheckCircle2 />
        <h2>You&apos;re in</h2>
        <p>You&apos;ve joined the workspace. Head to Content to get started.</p>
        <Link className="primary-button" href="/content">
          Go to workspace
        </Link>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="form-error" role="alert">
        {error ?? "This invite could not be accepted. It may have expired or already been used."}
      </div>
    );
  }

  const next = `/invite?token=${encodeURIComponent(token)}`;
  return (
    <div className="auth-form">
      <p>Sign in or create an account with the email address this invite was sent to, and we&apos;ll add you to the workspace.</p>
      <button className="primary-button" onClick={() => router.push(`/login?next=${encodeURIComponent(next)}`)}>
        Log in to accept
      </button>
      <button
        className="primary-button"
        onClick={() => router.push(`/signup?next=${encodeURIComponent(next)}`)}
      >
        Create an account
      </button>
    </div>
  );
}
