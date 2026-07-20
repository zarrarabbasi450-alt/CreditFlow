"use client";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import Link from "next/link";
export function SimpleAuthForm({ kind }: { kind: "forgot" | "reset" | "verify" | "invite" }) {
  const [done, setDone] = useState(false);
  if (done)
    return (
      <div className="success-state">
        <CheckCircle2 />
        <h2>Everything is ready</h2>
        <p>
          {kind === "forgot"
            ? "Check your inbox for a secure reset link."
            : kind === "verify"
              ? "Your email address has been verified."
              : kind === "invite"
                ? "You joined the Orion Media Group workspace."
                : "Your password has been updated securely."}
        </p>
        <Link className="primary-button" href="/login">
          Continue to sign in
        </Link>
      </div>
    );
  return (
    <form
      className="auth-form"
      onSubmit={(e) => {
        e.preventDefault();
        setDone(true);
      }}
    >
      {kind === "forgot" && (
        <div>
          <label htmlFor="email">Work email</label>
          <input id="email" type="email" required placeholder="you@company.com" />
        </div>
      )}
      {kind === "reset" && (
        <>
          <div>
            <label htmlFor="password">New password</label>
            <input id="password" type="password" required minLength={8} />
          </div>
          <div>
            <label htmlFor="confirm">Confirm password</label>
            <input id="confirm" type="password" required minLength={8} />
          </div>
        </>
      )}
      {kind === "invite" && (
        <>
          <div className="invite-card">
            <span>OM</span>
            <div>
              <strong>Orion Media Group</strong>
              <small>Invited by Avery Moore as Member</small>
            </div>
          </div>
          <div>
            <label htmlFor="name">Your name</label>
            <input id="name" required defaultValue="Jordan Lee" />
          </div>
          <div>
            <label htmlFor="password">Create password</label>
            <input id="password" type="password" required minLength={8} />
          </div>
        </>
      )}
      {kind === "verify" && (
        <div className="verify-copy">
          Click below to confirm <strong>avery@orionmedia.com</strong> as your CreditFlow email.
        </div>
      )}
      <button className="primary-button">
        {kind === "forgot"
          ? "Send reset link"
          : kind === "reset"
            ? "Update password"
            : kind === "invite"
              ? "Accept invitation"
              : "Verify email"}
      </button>
    </form>
  );
}
