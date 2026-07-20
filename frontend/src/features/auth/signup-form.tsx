"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
export function SignupForm() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { signup } = useAuth();
  const router = useRouter();
  return (
    <form
      className="auth-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        const data = new FormData(e.currentTarget);
        const password = String(data.get("password"));
        try {
          if (
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
          await signup(String(data.get("email")), password);
          router.push("/dashboard");
        } catch (reason) {
          setError((reason as Error).message);
          setLoading(false);
        }
      }}
    >
      <div>
        <label htmlFor="name">Full name</label>
        <input id="name" name="name" required minLength={2} placeholder="Avery Moore" />
      </div>
      <div>
        <label htmlFor="email">Work email</label>
        <input id="email" name="email" required type="email" placeholder="avery@company.com" />
      </div>
      <div>
        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          required
          type="password"
          minLength={8}
          placeholder="At least 8 characters"
        />
      </div>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      <button disabled={loading} className="primary-button">
        {loading ? "Creating workspace…" : "Create my workspace"}
      </button>
    </form>
  );
}
