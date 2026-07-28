"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { acceptInvite, createAccount } from "@/lib/api/tenants";

type Mode = "signup" | "invite";
type AccountType = "individual" | "team";

const slugify = (name: string) =>
  name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

function validatePassword(password: string) {
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
}

export function SignupForm() {
  const search = useSearchParams();
  const [mode, setMode] = useState<Mode>(search.get("token") ? "invite" : "signup");
  const [accountType, setAccountType] = useState<AccountType>("individual");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { signup, switchAccount } = useAuth();
  const router = useRouter();

  async function submitSignup(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const data = new FormData(e.currentTarget);
    const password = String(data.get("password"));
    const workspaceName = String(data.get("workspaceName") ?? "").trim();
    try {
      validatePassword(password);
      if (accountType === "team" && workspaceName.length < 2) {
        throw new Error("Workspace name must be at least 2 characters.");
      }
      const user = await signup(String(data.get("email")), password);
      if (accountType === "team") {
        const account = await createAccount({
          name: workspaceName,
          slug: slugify(workspaceName),
          type: "team",
        });
        await switchAccount(account.id);
      }
      const fallback = accountType === "team" || user.role === "Owner" ? "/dashboard" : "/content";
      router.push(search.get("next") ?? fallback);
    } catch (reason) {
      setError((reason as Error).message);
      setLoading(false);
    }
  }

  async function submitInvite(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const data = new FormData(e.currentTarget);
    const code = String(data.get("code")).trim();
    const password = String(data.get("password"));
    try {
      validatePassword(password);
      await signup(String(data.get("email")), password);
    } catch (reason) {
      setError((reason as Error).message);
      setLoading(false);
      return;
    }
    try {
      await acceptInvite(code);
      router.push("/content");
    } catch {
      // Account was created and the user is signed in — send them to the invite
      // page so they can see the specific error and retry without signing up again.
      router.push(`/invite?token=${encodeURIComponent(code)}`);
    }
  }

  return (
    <div>
      <div className="auth-mode-toggle">
        <button
          type="button"
          className={mode === "signup" ? "active" : undefined}
          onClick={() => setMode("signup")}
        >
          Sign up
        </button>
        <button
          type="button"
          className={mode === "invite" ? "active" : undefined}
          onClick={() => setMode("invite")}
        >
          Accept an invite
        </button>
      </div>
      <p className="auth-mode-hint">
        {mode === "signup"
          ? "This creates your account as the workspace Owner after email verification."
          : "Joining with an invite code adds you to an existing workspace — invited members do not need email verification."}
      </p>
      {mode === "signup" ? (
        <form className="auth-form" onSubmit={submitSignup}>
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
          <fieldset className="auth-account-type">
            <legend>Account type</legend>
            <label>
              <input
                type="radio"
                name="accountTypeChoice"
                checked={accountType === "individual"}
                onChange={() => setAccountType("individual")}
              />
              Individual — just me
            </label>
            <label>
              <input
                type="radio"
                name="accountTypeChoice"
                checked={accountType === "team"}
                onChange={() => setAccountType("team")}
              />
              Team — invite others later
            </label>
          </fieldset>
          {accountType === "team" && (
            <div>
              <label htmlFor="workspaceName">Workspace name</label>
              <input
                id="workspaceName"
                name="workspaceName"
                required
                minLength={2}
                placeholder="Orion Media Group"
              />
            </div>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <button disabled={loading} className="primary-button">
            {loading ? "Creating workspace…" : "Create owner account"}
          </button>
        </form>
      ) : (
        <form className="auth-form" onSubmit={submitInvite}>
          <div>
            <label htmlFor="code">Invite code or token</label>
            <input
              id="code"
              name="code"
              required
              minLength={4}
              defaultValue={search.get("token") ?? ""}
              placeholder="Paste owner-generated invite code"
            />
          </div>
          <div>
            <label htmlFor="invite-name">Full name</label>
            <input id="invite-name" name="name" required minLength={2} placeholder="Your full name" />
          </div>
          <div>
            <label htmlFor="invite-email">Email</label>
            <input id="invite-email" name="email" required type="email" placeholder="you@company.com" />
          </div>
          <div>
            <label htmlFor="invite-password">Password</label>
            <input
              id="invite-password"
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
            {loading ? "Joining workspace…" : "Join workspace"}
          </button>
        </form>
      )}
    </div>
  );
}
