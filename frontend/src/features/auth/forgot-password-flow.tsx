"use client";
import { useState } from "react";
import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { requestPasswordReset, resetPassword, verifyResetCode } from "@/lib/api/auth";

type Step = "request" | "verify" | "reset" | "done";

function validatePassword(password: string) {
  if (
    password.length < 8 ||
    password.length > 64 ||
    !/[A-Z]/.test(password) ||
    !/[a-z]/.test(password) ||
    !/\d/.test(password) ||
    !/[^A-Za-z0-9]/.test(password)
  ) {
    throw new Error(
      "Password must be 8–64 characters with uppercase, lowercase, number, and special character.",
    );
  }
}

export function ForgotPasswordFlow() {
  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset(email);
      setStep("verify");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send a reset code");
    } finally {
      setLoading(false);
    }
  }

  async function submitVerify(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await verifyResetCode(email, code);
      setStep("reset");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "That code is invalid or has expired");
    } finally {
      setLoading(false);
    }
  }

  async function submitReset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      validatePassword(password);
      await resetPassword(email, code, password);
      setStep("done");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reset your password");
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <div className="success-state">
        <CheckCircle2 />
        <h2>Password updated</h2>
        <p>Your password has been reset. All existing sessions were signed out for your security.</p>
        <Link className="primary-button" href="/login">
          Continue to sign in
        </Link>
      </div>
    );
  }

  return (
    <>
      {step === "request" && (
        <form className="auth-form" noValidate onSubmit={submitRequest}>
          <div>
            <label htmlFor="forgot-email">Work email</label>
            <input
              id="forgot-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
            />
          </div>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <button className="primary-button" disabled={loading}>
            {loading ? "Sending code…" : "Send reset code"}
          </button>
        </form>
      )}
      {step === "verify" && (
        <form className="auth-form" noValidate onSubmit={submitVerify}>
          <p className="auth-mode-hint">
            We sent a 6-digit code to <strong>{email}</strong>. It expires soon, so enter it below.
          </p>
          <div>
            <label htmlFor="forgot-code">6-digit code</label>
            <input
              id="forgot-code"
              required
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="123456"
            />
          </div>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <button className="primary-button" disabled={loading || code.length !== 6}>
            {loading ? "Checking…" : "Verify code"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={loading}
            onClick={() => {
              setStep("request");
              setCode("");
              setError(null);
            }}
          >
            Use a different email
          </button>
        </form>
      )}
      {step === "reset" && (
        <form className="auth-form" noValidate onSubmit={submitReset}>
          <div>
            <label htmlFor="forgot-password">New password</label>
            <input
              id="forgot-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <button className="primary-button" disabled={loading}>
            {loading ? "Updating…" : "Update password"}
          </button>
        </form>
      )}
    </>
  );
}
