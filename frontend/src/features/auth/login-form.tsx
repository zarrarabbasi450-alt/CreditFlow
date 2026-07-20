"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { loginSchema } from "@/lib/schemas";
import { useAuth } from "@/hooks/useAuth";
type Values = z.infer<typeof loginSchema>;
export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "owner@orionmedia.com", password: "Password123!" },
  });
  return (
    <form
      noValidate
      className="auth-form"
      onSubmit={handleSubmit(async (values) => {
        try {
          await login(values.email, values.password);
          router.push(search.get("next") ?? "/dashboard");
        } catch (error) {
          setError("root", { message: (error as Error).message });
        }
      })}
    >
      <div>
        <label htmlFor="email">Work email</label>
        <input id="email" type="email" autoComplete="email" {...register("email")} />
        {errors.email && <p role="alert">{errors.email.message}</p>}
      </div>
      <div>
        <div className="label-row">
          <label htmlFor="password">Password</label>
          <Link href="/forgot-password">Forgot password?</Link>
        </div>
        <input id="password" type="password" autoComplete="current-password" {...register("password")} />
        {errors.password && <p role="alert">{errors.password.message}</p>}
      </div>
      {errors.root && (
        <div className="form-error" role="alert">
          {errors.root.message}
        </div>
      )}
      <button className="primary-button" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in to CreditFlow"}
      </button>
    </form>
  );
}
